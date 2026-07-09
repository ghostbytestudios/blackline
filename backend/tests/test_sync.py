"""Sync upsert logic: idempotency, pending->posted updates, type inference."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.integrations.simplefin import NormAccount, NormHolding, NormTxn, SyncPayload
from app.models import Account, Transaction
from app.services import sync as sync_service


def _payload(*, pending=False, balance=123_456) -> SyncPayload:
    when = datetime(2026, 7, 1, tzinfo=timezone.utc)
    return SyncPayload(
        accounts=[
            NormAccount(
                external_id="acct-1",
                org_name="Demo Bank",
                name="Everyday Checking",
                currency="USD",
                balance_minor=balance,
                available_minor=balance,
                balance_date=when,
                transactions=[
                    NormTxn("txn-1", when, -4_500, "STARBUCKS #12", "Starbucks", None, pending),
                    NormTxn("txn-2", when, 260_000, "ACME DIRECT DEPOSIT", "Acme Corp", None, False),
                ],
                holdings=[],
            ),
            NormAccount(
                external_id="acct-2",
                org_name="Broker",
                name="Brokerage",
                currency="USD",
                balance_minor=1_000_000,
                available_minor=None,
                balance_date=when,
                transactions=[],
                holdings=[
                    NormHolding("h-1", "VTI", "Vanguard Total Market", "10.5", 950_000, 800_000, "USD", when),
                ],
            ),
        ],
        errors=[],
    )


def run(db, monkeypatch, payload: SyncPayload):
    monkeypatch.setattr(sync_service, "_get_access_url", lambda _db: "https://unused")
    monkeypatch.setattr(sync_service.simplefin, "fetch_accounts", lambda url, start_date: payload)
    return sync_service.run_sync(db)


def test_first_sync_inserts_everything(db, monkeypatch, tmp_data_dir):
    result = run(db, monkeypatch, _payload())
    assert result.accounts_upserted == 2
    assert result.transactions_inserted == 2
    assert result.holdings_upserted == 1
    assert db.scalar(select(Account).where(Account.external_id == "acct-1")).name == "Everyday Checking"


def test_resync_is_idempotent(db, monkeypatch, tmp_data_dir):
    run(db, monkeypatch, _payload())
    result = run(db, monkeypatch, _payload())
    assert result.transactions_inserted == 0  # nothing duplicated
    assert len(list(db.scalars(select(Transaction)))) == 2
    assert len(list(db.scalars(select(Account)))) == 2


def test_pending_transition_updates_in_place(db, monkeypatch, tmp_data_dir):
    run(db, monkeypatch, _payload(pending=True))
    txn = db.scalar(select(Transaction).where(Transaction.external_id == "txn-1"))
    assert txn.pending is True

    run(db, monkeypatch, _payload(pending=False))
    db.refresh(txn)
    assert txn.pending is False
    assert len(list(db.scalars(select(Transaction)))) == 2


def test_user_category_survives_resync(db, monkeypatch, tmp_data_dir):
    run(db, monkeypatch, _payload())
    txn = db.scalar(select(Transaction).where(Transaction.external_id == "txn-1"))
    assert txn.category == "dining"  # auto-categorized by keyword
    txn.category = "office-coffee"
    txn.category_source = "user"
    db.commit()

    run(db, monkeypatch, _payload())
    db.refresh(txn)
    assert txn.category == "office-coffee"


def test_balance_updates_on_resync(db, monkeypatch, tmp_data_dir):
    run(db, monkeypatch, _payload(balance=100_000))
    run(db, monkeypatch, _payload(balance=99_000))
    acct = db.scalar(select(Account).where(Account.external_id == "acct-1"))
    assert acct.balance_minor == 99_000


def test_account_with_holdings_inferred_investment(db, monkeypatch, tmp_data_dir):
    run(db, monkeypatch, _payload())
    broker = db.scalar(select(Account).where(Account.external_id == "acct-2"))
    assert broker.account_type == "investment"


def test_type_inference_from_name():
    def norm(name):
        return NormAccount(
            external_id="x", org_name=None, name=name, currency="USD",
            balance_minor=0, available_minor=None, balance_date=None,
        )

    assert sync_service._infer_type(norm("Sapphire Visa Card")) == "credit"
    assert sync_service._infer_type(norm("Home Mortgage")) == "loan"
    assert sync_service._infer_type(norm("Everyday Checking")) == "depository"
