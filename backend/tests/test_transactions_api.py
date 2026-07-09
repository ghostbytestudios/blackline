"""Transaction search, tag filtering, and note/tags annotation (router-level)."""

from __future__ import annotations

from app.routers.transactions import annotate_transaction, list_transactions, normalize_tags
from app.schemas import TransactionAnnotate, TransactionOut

from .helpers import make_account, make_txn


def test_normalize_tags():
    assert normalize_tags([" Work ", "WORK", "tax, deductible", ""]) == "work,tax deductible"


def test_search_matches_payee_description_and_note(db):
    acct = make_account(db)
    t1 = make_txn(db, acct, amount_minor=-1_000, payee="Starbucks", description="STARBUCKS #12")
    t2 = make_txn(db, acct, amount_minor=-2_000, payee="Kroger", description="KROGER #99")
    t2.note = "coffee beans for the office"
    db.commit()

    ids = {t.id for t in list_transactions(db=db, q="starbucks")}
    assert ids == {t1.id}
    # Note text is searchable too.
    ids = {t.id for t in list_transactions(db=db, q="coffee")}
    assert ids == {t2.id}
    assert list_transactions(db=db, q="zzz-no-match") == []


def test_tag_filter_matches_whole_tags_only(db):
    acct = make_account(db)
    t1 = make_txn(db, acct, amount_minor=-1_000, payee="A")
    t2 = make_txn(db, acct, amount_minor=-2_000, payee="B")
    t1.tags = "work,travel"
    t2.tags = "workshop"
    db.commit()

    ids = {t.id for t in list_transactions(db=db, tag="work")}
    assert ids == {t1.id}  # "workshop" must not match tag "work"


def test_annotate_sets_note_and_normalized_tags(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-1_000, payee="A")
    result = annotate_transaction(
        txn.id, TransactionAnnotate(note="  split with Sam  ", tags=["Trip", "trip", " Work "]), db=db
    )
    assert result.note == "split with Sam"
    assert result.tags == "trip,work"
    out = TransactionOut.model_validate(result)
    assert out.tags == ["trip", "work"]


def test_annotate_partial_update_preserves_other_field(db):
    acct = make_account(db)
    txn = make_txn(db, acct, amount_minor=-1_000, payee="A")
    annotate_transaction(txn.id, TransactionAnnotate(note="keep me"), db=db)
    annotate_transaction(txn.id, TransactionAnnotate(tags=["one"]), db=db)
    db.refresh(txn)
    assert txn.note == "keep me"
    assert txn.tags == "one"
    # Empty note clears it.
    annotate_transaction(txn.id, TransactionAnnotate(note="  "), db=db)
    db.refresh(txn)
    assert txn.note is None
