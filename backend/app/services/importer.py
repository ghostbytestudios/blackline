"""CSV/OFX statement import: parse, map columns, dedup, insert.

Files arrive as text (JSON body, not multipart) — bank exports are small. Two
formats:

- **CSV** — delimiter sniffed, header detected, column mapping suggested from
  header names and refined by the user in the UI. Dates auto-detected against a
  format list; amounts accept $/commas/parentheses/trailing-minus and European
  decimal commas.
- **OFX/QFX** — both SGML (1.x, unclosed tags) and XML (2.x) flavors, parsed
  with a tolerant regex scan of <STMTTRN> blocks. FITID gives a stable id.

Dedup happens at two levels on commit:
1. Deterministic external_id per row (OFX FITID, or a CSV content hash with an
   occurrence counter) — re-importing the same file inserts nothing.
2. Heuristic overlap with synced data: an existing transaction on the same
   account with the same amount within ±3 days absorbs one candidate row.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, CategoryRule, Transaction
from ..schemas import ColumnMapping, ImportPreview, ImportResult
from . import categorize

_MAX_SAMPLE_ROWS = 8
_DUP_WINDOW_DAYS = 3

# Tried in order; the first format that parses every sampled value wins, so US
# month-first outranks day-first unless a value >12 rules it out.
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%m/%d/%y",
    "%d/%m/%y",
    "%Y%m%d",
    "%b %d, %Y",
    "%d %b %Y",
    "%B %d, %Y",
]

_HEADER_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("date", ("transaction date", "post date", "posted", "date")),
    ("amount", ("amount", "amt", "value")),
    ("debit", ("debit", "withdrawal", "money out", "outflow", "spent")),
    ("credit", ("credit", "deposit", "money in", "inflow", "received")),
    ("payee", ("payee", "merchant", "name")),
    ("description", ("description", "details", "narrative")),
    ("memo", ("memo", "notes", "note", "reference")),
]


@dataclass
class ParsedRow:
    posted: date
    amount_minor: int
    payee: str | None = None
    description: str = ""
    memo: str | None = None
    fitid: str | None = None  # OFX only


@dataclass
class ParsedFile:
    kind: str  # "csv" | "ofx"
    rows: list[ParsedRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    currency: str | None = None  # OFX CURDEF, if present


class ImportError_(ValueError):
    """Raised when a file can't be parsed at all (bad format, no usable rows)."""


# ---------------------------------------------------------------------------
# Value parsing


def parse_amount_minor(raw: str) -> int | None:
    """'$1,234.56' / '(45.00)' / '45.00-' / '1.234,56' -> signed minor units."""
    s = raw.strip()
    for sym in ("$", "€", "£", "\xa0", " "):
        s = s.replace(sym, "")
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.endswith("-"):
        negative, s = True, s[:-1]
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        negative, s = True, s[1:]
    # Disambiguate thousands vs decimal separators.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")  # 1.234,56 (European)
        else:
            s = s.replace(",", "")  # 1,234.56
    elif "," in s:
        if re.fullmatch(r"\d+,\d{1,2}", s):
            s = s.replace(",", ".")  # 12,34 decimal comma
        else:
            s = s.replace(",", "")  # 1,234
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        return None
    try:
        minor = int((Decimal(s) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None
    return -minor if negative else minor


def parse_date(raw: str, fmt: str | None = None) -> date | None:
    s = raw.strip()
    if "T" in s:  # ISO datetime — keep the date part
        s = s.split("T", 1)[0]
    if fmt:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            return None
    for candidate in _DATE_FORMATS:
        try:
            return datetime.strptime(s, candidate).date()
        except ValueError:
            continue
    return None


def detect_date_format(values: list[str]) -> str | None:
    """First format that parses every non-empty sampled value."""
    samples = [v.strip().split("T", 1)[0] for v in values if v.strip()][:50]
    if not samples:
        return None
    for fmt in _DATE_FORMATS:
        try:
            for s in samples:
                datetime.strptime(s, fmt)
            return fmt
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# CSV


def _sniff_delimiter(text: str) -> str:
    first_lines = "\n".join(text.splitlines()[:10])
    try:
        return csv.Sniffer().sniff(first_lines, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _read_csv(text: str) -> tuple[list[str], list[list[str]]]:
    """Returns (headers, data_rows). Headers are synthesized if the file has none."""
    delimiter = _sniff_delimiter(text)
    rows = [
        row
        for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        raise ImportError_("The file contains no rows.")
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # Header row: no cell parses as a date and no cell parses as a money amount.
    first = rows[0]
    looks_like_header = not any(parse_date(c) for c in first) and not any(
        parse_amount_minor(c) is not None and any(ch.isdigit() for ch in c) for c in first
    )
    if looks_like_header:
        headers = [c.strip() or f"Column {i + 1}" for i, c in enumerate(first)]
        return headers, rows[1:]
    return [f"Column {i + 1}" for i in range(width)], rows


def suggest_mapping(headers: list[str], data_rows: list[list[str]]) -> ColumnMapping | None:
    """Guess the column mapping from header names, falling back to content shape."""
    assigned: dict[str, int] = {}
    used: set[int] = set()
    lowered = [h.lower().strip() for h in headers]
    for field_name, hints in _HEADER_HINTS:
        for hint in hints:
            found = next(
                (i for i, h in enumerate(lowered) if hint in h and i not in used), None
            )
            if found is not None:
                assigned[field_name] = found
                used.add(found)
                break

    sample = data_rows[:20]
    if "date" not in assigned:
        for i in range(len(headers)):
            if i not in used and sample and all(parse_date(r[i]) for r in sample if r[i].strip()):
                if any(r[i].strip() for r in sample):
                    assigned["date"] = i
                    used.add(i)
                    break
    if "amount" not in assigned and "debit" not in assigned and "credit" not in assigned:
        # Last unclaimed numeric column is usually the amount.
        for i in reversed(range(len(headers))):
            if i in used or not sample:
                continue
            cells = [r[i] for r in sample if r[i].strip()]
            if cells and all(parse_amount_minor(c) is not None for c in cells):
                assigned["amount"] = i
                used.add(i)
                break
    if "payee" not in assigned and "description" not in assigned:
        # Longest remaining text column.
        best, best_len = None, 0
        for i in range(len(headers)):
            if i in used:
                continue
            total = sum(len(r[i].strip()) for r in sample)
            if total > best_len:
                best, best_len = i, total
        if best is not None and best_len > 0:
            assigned["description"] = best

    if "date" not in assigned:
        return None
    date_values = [r[assigned["date"]] for r in data_rows[:50]]
    return ColumnMapping(**assigned, date_format=detect_date_format(date_values))


def _rows_from_csv(
    headers: list[str], data_rows: list[list[str]], mapping: ColumnMapping
) -> tuple[list[ParsedRow], list[str]]:
    def cell(row: list[str], idx: int | None) -> str:
        if idx is None or idx >= len(row):
            return ""
        return row[idx].strip()

    fmt = mapping.date_format or detect_date_format(
        [cell(r, mapping.date) for r in data_rows[:50]]
    )
    rows: list[ParsedRow] = []
    warnings: list[str] = []
    for line_no, row in enumerate(data_rows, start=2):
        posted = parse_date(cell(row, mapping.date), fmt)
        if posted is None:
            warnings.append(f"Row {line_no}: unreadable date {cell(row, mapping.date)!r}")
            continue
        amount: int | None = None
        if mapping.amount is not None:
            amount = parse_amount_minor(cell(row, mapping.amount))
            if amount is not None and mapping.flip_amounts:
                amount = -amount
        else:
            debit = parse_amount_minor(cell(row, mapping.debit)) if mapping.debit is not None else None
            credit = parse_amount_minor(cell(row, mapping.credit)) if mapping.credit is not None else None
            if debit is not None and debit != 0:
                amount = -abs(debit)
            elif credit is not None:
                amount = abs(credit)
        if amount is None:
            warnings.append(f"Row {line_no}: unreadable amount")
            continue
        rows.append(
            ParsedRow(
                posted=posted,
                amount_minor=amount,
                payee=cell(row, mapping.payee) or None,
                description=cell(row, mapping.description),
                memo=cell(row, mapping.memo) or None,
            )
        )
    return rows, warnings


# ---------------------------------------------------------------------------
# OFX / QFX


def _stmttrn_blocks(text: str) -> list[str]:
    """Linear scan for <STMTTRN> blocks — no backtracking regex over untrusted
    file content (a crafted file could make one run polynomially slow). SGML OFX
    often omits </STMTTRN>, so a block ends at the next opening tag, a closing
    tag, </BANKTRANLIST>, or end of file, whichever comes first."""
    upper = text.upper()
    open_tag = "<STMTTRN>"
    blocks: list[str] = []
    pos = upper.find(open_tag)
    while pos != -1:
        start = pos + len(open_tag)
        next_open = upper.find(open_tag, start)
        ends = [
            e
            for e in (
                upper.find("</STMTTRN>", start),
                upper.find("</BANKTRANLIST>", start),
                next_open,
            )
            if e != -1
        ]
        blocks.append(text[start : min(ends) if ends else len(text)])
        pos = next_open
    return blocks


def _ofx_field(block: str, tag: str) -> str | None:
    # SGML OFX has no closing tags: a value runs to end-of-line or the next tag.
    m = re.search(rf"<{tag}>([^<\r\n]*)", block, re.I)
    if m is None:
        return None
    value = html.unescape(m.group(1)).strip()
    return value or None


def _ofx_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    digits = raw.strip()[:8]
    if len(digits) != 8 or not digits.isdigit():
        return None
    try:
        return datetime.strptime(digits, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_ofx(text: str) -> ParsedFile:
    parsed = ParsedFile(kind="ofx", currency=_ofx_field(text, "CURDEF"))
    for i, block in enumerate(_stmttrn_blocks(text), start=1):
        posted = _ofx_date(_ofx_field(block, "DTPOSTED"))
        amount = parse_amount_minor(_ofx_field(block, "TRNAMT") or "")
        if posted is None or amount is None:
            parsed.warnings.append(f"Transaction {i}: missing/unreadable DTPOSTED or TRNAMT")
            continue
        parsed.rows.append(
            ParsedRow(
                posted=posted,
                amount_minor=amount,
                payee=_ofx_field(block, "NAME"),
                description=_ofx_field(block, "MEMO") or _ofx_field(block, "NAME") or "",
                memo=_ofx_field(block, "MEMO"),
                fitid=_ofx_field(block, "FITID"),
            )
        )
    if not parsed.rows and not parsed.warnings:
        raise ImportError_("No transactions found in the OFX file.")
    return parsed


# ---------------------------------------------------------------------------
# Entry points


def detect_kind(filename: str, content: str) -> str:
    lower = filename.lower()
    if lower.endswith((".ofx", ".qfx")):
        return "ofx"
    head = content[:2000].upper()
    if "<OFX" in head or "OFXHEADER" in head:
        return "ofx"
    return "csv"


def build_preview(filename: str, content: str) -> ImportPreview:
    kind = detect_kind(filename, content)
    if kind == "ofx":
        parsed = _parse_ofx(content)
        sample = [
            [str(r.posted), f"{r.amount_minor / 100:.2f}", r.payee or "", r.description]
            for r in parsed.rows[:_MAX_SAMPLE_ROWS]
        ]
        return ImportPreview(
            kind="ofx",
            headers=["Date", "Amount", "Payee", "Memo"],
            sample_rows=sample,
            row_count=len(parsed.rows),
            currency=parsed.currency,
            warnings=parsed.warnings[:10],
        )
    headers, data_rows = _read_csv(content)
    if not data_rows:
        raise ImportError_("The file has a header but no data rows.")
    return ImportPreview(
        kind="csv",
        headers=headers,
        sample_rows=[r[: len(headers)] for r in data_rows[:_MAX_SAMPLE_ROWS]],
        row_count=len(data_rows),
        suggested_mapping=suggest_mapping(headers, data_rows),
        warnings=[],
    )


def parse_file(filename: str, content: str, mapping: ColumnMapping | None) -> ParsedFile:
    kind = detect_kind(filename, content)
    if kind == "ofx":
        return _parse_ofx(content)
    if mapping is None:
        raise ImportError_("A column mapping is required for CSV imports.")
    headers, data_rows = _read_csv(content)
    rows, warnings = _rows_from_csv(headers, data_rows, mapping)
    if not rows and warnings:
        raise ImportError_(
            f"No rows could be parsed with this mapping (first problem: {warnings[0]})."
        )
    return ParsedFile(kind="csv", rows=rows, warnings=warnings)


def _row_external_id(row: ParsedRow, occurrence: int) -> str:
    if row.fitid:
        return f"import-ofx-{row.fitid}"
    seed = f"{row.posted.isoformat()}|{row.amount_minor}|{(row.payee or row.description).lower()}|{occurrence}"
    return f"import-csv-{hashlib.sha256(seed.encode()).hexdigest()[:20]}"


def commit_import(
    db: Session,
    account: Account,
    parsed: ParsedFile,
    *,
    skip_duplicates: bool = True,
) -> ImportResult:
    """Insert parsed rows into `account`, skipping exact and probable duplicates."""
    rules = list(db.scalars(select(CategoryRule).order_by(CategoryRule.priority.asc())))
    existing_ids = set(
        db.scalars(select(Transaction.external_id).where(Transaction.account_id == account.id))
    )

    # Heuristic dedup pool: existing transactions near the imported date range,
    # keyed by amount. Each can absorb at most one imported row.
    pool: dict[int, list[date]] = {}
    if skip_duplicates and parsed.rows:
        lo = min(r.posted for r in parsed.rows) - timedelta(days=_DUP_WINDOW_DAYS)
        hi = max(r.posted for r in parsed.rows) + timedelta(days=_DUP_WINDOW_DAYS)
        for txn in db.scalars(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.posted_at >= datetime.combine(lo, datetime.min.time(), timezone.utc),
                Transaction.posted_at <= datetime.combine(hi, datetime.max.time(), timezone.utc),
            )
        ):
            pool.setdefault(txn.amount_minor, []).append(txn.posted_at.date())

    inserted = 0
    duplicates = 0
    occurrences: dict[tuple, int] = {}
    for row in parsed.rows:
        occ_key = (row.posted, row.amount_minor, (row.payee or row.description).lower())
        occurrences[occ_key] = occurrences.get(occ_key, 0) + 1
        external_id = _row_external_id(row, occurrences[occ_key])
        if external_id in existing_ids:
            duplicates += 1
            continue
        if skip_duplicates:
            near = pool.get(row.amount_minor, [])
            match = next(
                (d for d in near if abs((d - row.posted).days) <= _DUP_WINDOW_DAYS), None
            )
            if match is not None:
                near.remove(match)
                duplicates += 1
                continue
        category = categorize.categorize_text(
            row.payee,
            row.description,
            rules,
            amount_minor=row.amount_minor,
            account_type=account.account_type,
        )
        db.add(
            Transaction(
                account_id=account.id,
                external_id=external_id,
                posted_at=datetime.combine(row.posted, datetime.min.time(), timezone.utc),
                amount_minor=row.amount_minor,
                description=row.description,
                payee=row.payee,
                memo=row.memo,
                pending=False,
                category=category,
                category_source="auto",
            )
        )
        existing_ids.add(external_id)
        inserted += 1

    if inserted:
        # New rows may be the missing leg of an internal transfer.
        from .transfers import match_transfers

        db.flush()
        match_transfers(db)
    db.commit()
    return ImportResult(
        total_rows=len(parsed.rows),
        inserted=inserted,
        duplicates_skipped=duplicates,
        unparsed_skipped=len(parsed.warnings),
        warnings=parsed.warnings[:10],
    )
