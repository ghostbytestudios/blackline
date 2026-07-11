"""CSV/OFX statement import: parsing, mapping suggestion, dedup, idempotency."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models import Transaction
from app.schemas import ColumnMapping
from app.services import importer

from .helpers import make_account, make_txn

CSV_BASIC = """Date,Description,Amount
2026-06-01,STARBUCKS #123,-6.45
2026-06-02,PAYROLL ACME CORP,2500.00
2026-06-03,"NETFLIX, INC",-15.99
"""

CSV_DEBIT_CREDIT = """Post Date,Payee,Debit,Credit
06/01/2026,GROCERY MART,54.20,
06/05/2026,REFUND SHOES,,29.99
"""

OFX_SGML = """OFXHEADER:100
DATA:OFXSGML

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>USD
<BANKACCTFROM><ACCTID>12345</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260601120000[-5:EST]
<TRNAMT>-6.45
<FITID>F-001
<NAME>STARBUCKS #123
<MEMO>coffee
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260602
<TRNAMT>2500.00
<FITID>F-002
<NAME>PAYROLL ACME &amp; CO
</STMTTRN>
</BANKTRANLIST>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""


# --- value parsing -----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "minor"),
    [
        ("1,234.56", 123456),
        ("$-45.00", -4500),
        ("(45.00)", -4500),
        ("45.00-", -4500),
        ("1.234,56", 123456),  # European
        ("12,34", 1234),  # decimal comma
        ("+10", 1000),
        ("0.005", 1),  # ROUND_HALF_UP
    ],
)
def test_parse_amount(raw, minor):
    assert importer.parse_amount_minor(raw) == minor


def test_parse_amount_rejects_garbage():
    assert importer.parse_amount_minor("N/A") is None
    assert importer.parse_amount_minor("") is None


def test_date_format_detection_prefers_month_first_until_disproven():
    assert importer.detect_date_format(["01/02/2026", "03/04/2026"]) == "%m/%d/%Y"
    # A day > 12 forces day-first.
    assert importer.detect_date_format(["13/02/2026", "03/04/2026"]) == "%d/%m/%Y"


# --- preview / mapping suggestion --------------------------------------------


def test_preview_csv_suggests_mapping():
    p = importer.build_preview("statement.csv", CSV_BASIC)
    assert p.kind == "csv"
    assert p.row_count == 3
    assert p.headers == ["Date", "Description", "Amount"]
    m = p.suggested_mapping
    assert m is not None
    assert (m.date, m.description, m.amount) == (0, 1, 2)
    assert m.date_format == "%Y-%m-%d"


def test_preview_csv_debit_credit_columns():
    m = importer.build_preview("s.csv", CSV_DEBIT_CREDIT).suggested_mapping
    assert m is not None
    assert (m.date, m.payee, m.debit, m.credit) == (0, 1, 2, 3)
    assert m.amount is None


def test_preview_headerless_csv_synthesizes_columns():
    p = importer.build_preview("x.csv", "2026-06-01,COFFEE,-4.50\n2026-06-02,LUNCH,-12.00\n")
    assert p.headers == ["Column 1", "Column 2", "Column 3"]
    assert p.row_count == 2
    m = p.suggested_mapping
    assert m is not None and m.date == 0 and m.amount == 2


def test_preview_ofx():
    p = importer.build_preview("statement.qfx", OFX_SGML)
    assert p.kind == "ofx"
    assert p.row_count == 2
    assert p.currency == "USD"


def test_preview_empty_file_raises():
    with pytest.raises(importer.ImportError_):
        importer.build_preview("empty.csv", "   \n  ")


# --- OFX parsing --------------------------------------------------------------


def test_ofx_hostile_input_parses_fast():
    """CodeQL #4 regression: block extraction must stay linear on malformed
    files — an open tag followed by megabytes of junk and no terminator."""
    import time

    hostile = "OFXHEADER:100\n<OFX><BANKTRANLIST><STMTTRN>\n" + "a" * 2_000_000
    start = time.perf_counter()
    parsed = importer._parse_ofx(hostile)
    assert time.perf_counter() - start < 2.0
    # One block found (unterminated -> runs to EOF), unparseable -> warning.
    assert parsed.rows == []
    assert len(parsed.warnings) == 1


def test_ofx_rows_parsed():
    parsed = importer.parse_file("s.ofx", OFX_SGML, None)
    assert [r.fitid for r in parsed.rows] == ["F-001", "F-002"]
    assert parsed.rows[0].posted == date(2026, 6, 1)
    assert parsed.rows[0].amount_minor == -645
    assert parsed.rows[1].payee == "PAYROLL ACME & CO"  # entity unescaped


# --- commit: insert, categorize, dedup ----------------------------------------


def _commit_csv(db, account, text, mapping, **kw):
    parsed = importer.parse_file("s.csv", text, mapping)
    return importer.commit_import(db, account, parsed, **kw)


def test_commit_inserts_and_categorizes(db):
    acct = make_account(db)
    mapping = ColumnMapping(date=0, description=1, amount=2)
    result = _commit_csv(db, acct, CSV_BASIC, mapping)
    assert (result.inserted, result.duplicates_skipped) == (3, 0)
    txns = list(db.scalars(select(Transaction)))
    assert len(txns) == 3
    by_desc = {t.description: t for t in txns}
    assert by_desc["STARBUCKS #123"].amount_minor == -645
    assert by_desc["STARBUCKS #123"].category != "uncategorized"  # keyword map hit
    assert all(t.external_id.startswith("import-csv-") for t in txns)


def test_reimporting_same_file_is_idempotent(db):
    acct = make_account(db)
    mapping = ColumnMapping(date=0, description=1, amount=2)
    _commit_csv(db, acct, CSV_BASIC, mapping)
    again = _commit_csv(db, acct, CSV_BASIC, mapping)
    assert again.inserted == 0
    assert again.duplicates_skipped == 3


def test_identical_rows_within_file_both_import(db):
    # Two genuinely identical charges on the same day (e.g. two coffees) must
    # not collapse into one — the occurrence counter keeps their ids distinct.
    text = "Date,Description,Amount\n2026-06-01,COFFEE,-4.50\n2026-06-01,COFFEE,-4.50\n"
    acct = make_account(db)
    result = _commit_csv(db, acct, text, ColumnMapping(date=0, description=1, amount=2))
    assert result.inserted == 2


def test_heuristic_dedup_against_synced_data(db):
    acct = make_account(db)
    # A synced transaction: same amount, one day off from the import row.
    synced = make_txn(db, acct, amount_minor=-645, payee="STARBUCKS")
    synced.posted_at = datetime(2026, 6, 2, tzinfo=timezone.utc)
    db.flush()
    mapping = ColumnMapping(date=0, description=1, amount=2)
    result = _commit_csv(db, acct, CSV_BASIC, mapping)
    assert result.duplicates_skipped == 1
    assert result.inserted == 2


def test_skip_duplicates_false_imports_everything(db):
    acct = make_account(db)
    synced = make_txn(db, acct, amount_minor=-645)
    synced.posted_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    db.flush()
    mapping = ColumnMapping(date=0, description=1, amount=2)
    result = _commit_csv(db, acct, CSV_BASIC, mapping, skip_duplicates=False)
    assert result.inserted == 3


def test_flip_amounts(db):
    text = "Date,Description,Amount\n2026-06-01,COFFEE,4.50\n"
    acct = make_account(db)
    _commit_csv(db, acct, text, ColumnMapping(date=0, description=1, amount=2, flip_amounts=True))
    txn = db.scalar(select(Transaction))
    assert txn.amount_minor == -450


def test_debit_credit_commit(db):
    acct = make_account(db)
    m = importer.build_preview("s.csv", CSV_DEBIT_CREDIT).suggested_mapping
    result = _commit_csv(db, acct, CSV_DEBIT_CREDIT, m)
    assert result.inserted == 2
    amounts = sorted(t.amount_minor for t in db.scalars(select(Transaction)))
    assert amounts == [-5420, 2999]


def test_ofx_commit_idempotent_by_fitid(db):
    acct = make_account(db)
    parsed = importer.parse_file("s.ofx", OFX_SGML, None)
    first = importer.commit_import(db, acct, parsed)
    assert first.inserted == 2
    again = importer.commit_import(db, acct, importer.parse_file("s.ofx", OFX_SGML, None))
    assert again.inserted == 0 and again.duplicates_skipped == 2


def test_bad_rows_counted_not_fatal(db):
    text = "Date,Description,Amount\n2026-06-01,OK,-1.00\nnot-a-date,BAD,-2.00\n"
    acct = make_account(db)
    result = _commit_csv(db, acct, text, ColumnMapping(date=0, description=1, amount=2))
    assert result.inserted == 1
    assert result.unparsed_skipped == 1
    assert result.warnings
