"""SimpleFIN Bridge client.

Protocol (https://www.simplefin.org/protocol.html):
  1. User creates a *Setup Token* (base64 of a one-time "claim URL").
  2. We POST to the claim URL once to exchange it for an *Access URL* of the form
     `https://USER:PASS@host/simplefin`. This is a read-only bearer credential.
  3. We GET `{access}/accounts` with HTTP Basic auth to pull accounts + transactions.

Security posture:
  - HTTPS is required; the host must be within the configured allowlist (egress control).
  - The access URL / credentials are never logged.
  - All returned fields are treated as untrusted and normalized before use.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import httpx

from ..config import get_settings

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class SimpleFINError(Exception):
    pass


# --- Normalized data structures (decoupled from the wire format) ---
@dataclass
class NormTxn:
    external_id: str
    posted_at: datetime
    amount_minor: int
    description: str
    payee: str | None
    memo: str | None
    pending: bool


@dataclass
class NormHolding:
    external_id: str
    symbol: str | None
    description: str | None
    shares: str | None
    market_value_minor: int | None
    cost_basis_minor: int | None
    currency: str
    as_of: datetime | None


@dataclass
class NormAccount:
    external_id: str
    org_name: str | None
    name: str
    currency: str
    balance_minor: int
    available_minor: int | None
    balance_date: datetime | None
    transactions: list[NormTxn] = field(default_factory=list)
    holdings: list[NormHolding] = field(default_factory=list)


@dataclass
class SyncPayload:
    accounts: list[NormAccount]
    errors: list[str]


# --- Helpers ---
def _allowed_hosts() -> set[str]:
    """Exact-match egress allowlist (comma-separated in config). No wildcarding:
    an unexpected subdomain is refused until the user explicitly allows it."""
    raw = get_settings().simplefin_allowed_host
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _validate_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise SimpleFINError("refusing non-HTTPS SimpleFIN URL")
    host = (parts.hostname or "").lower()
    if host not in _allowed_hosts():
        raise SimpleFINError(
            f"SimpleFIN host {host!r} is outside the allowlist; refusing egress. "
            "Self-hosting a bridge? Add its host to BLACKLINE_SIMPLEFIN_ALLOWED_HOST."
        )


def _rebuild_for_request(url: str) -> str:
    """Validate, then reconstruct the URL from its parsed components so the request
    target can only contain the validated host — a raw string could smuggle
    `user@evil.com` userinfo or a fragment past a naive substring check."""
    _validate_host(url)
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit(("https", netloc, parts.path, parts.query, ""))


def _to_minor(amount: str | int | float | None, currency: str = "USD") -> int | None:
    """Convert a decimal amount string to integer minor units (cents).

    SimpleFIN sends amounts as decimal strings, e.g. "-33.45".
    """
    if amount is None:
        return None
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise SimpleFINError(f"invalid monetary amount: {amount!r}") from exc
    # Assume 2 minor digits (USD and most listed currencies). Quantize defensively.
    return int((d * 100).quantize(Decimal("1")))


def _epoch_to_dt(value) -> datetime | None:  # noqa: ANN001
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, OSError, TypeError):
        return None


def decode_setup_token(setup_token: str) -> str:
    """Decode a base64 Setup Token into its claim URL."""
    token = setup_token.strip()
    try:
        claim_url = base64.b64decode(token, validate=True).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise SimpleFINError("setup token is not valid base64") from exc
    _validate_host(claim_url)
    return claim_url


def claim_access_url(setup_token: str) -> str:
    """Exchange a one-time Setup Token for a durable Access URL. Network call."""
    claim_url = _rebuild_for_request(decode_setup_token(setup_token))
    try:
        # Redirects stay off (also httpx's default) so the validated host is the
        # only place this request can ever land.
        resp = httpx.post(claim_url, timeout=_TIMEOUT, follow_redirects=False)
        if resp.is_redirect:
            raise SimpleFINError("SimpleFIN claim endpoint tried to redirect; refusing")
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SimpleFINError("failed to claim SimpleFIN access URL") from exc
    access_url = resp.text.strip()
    _validate_host(access_url)
    return access_url


def fetch_accounts(access_url: str, start_date: datetime | None = None) -> SyncPayload:
    """Pull accounts, balances, transactions and holdings. Network call."""
    _validate_host(access_url)
    parts = urlsplit(access_url)
    auth = (parts.username or "", parts.password or "")
    # Reconstruct the base URL without embedded credentials.
    base = f"{parts.scheme}://{parts.hostname}"
    if parts.port:
        base += f":{parts.port}"
    base += parts.path
    endpoint = base.rstrip("/") + "/accounts"

    params: dict[str, str] = {"pending": "1"}
    if start_date is not None:
        params["start-date"] = str(int(start_date.timestamp()))

    try:
        resp = httpx.get(
            endpoint, params=params, auth=auth, timeout=_TIMEOUT, follow_redirects=False
        )
        if resp.is_redirect:
            raise SimpleFINError("SimpleFIN endpoint tried to redirect; refusing")
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise SimpleFINError("SimpleFIN sync request failed") from exc
    except ValueError as exc:
        raise SimpleFINError("SimpleFIN returned non-JSON response") from exc

    return _normalize(data)


def _normalize(data: dict) -> SyncPayload:
    errors = [str(e) for e in data.get("errors", []) or []]
    accounts: list[NormAccount] = []

    for raw in data.get("accounts", []) or []:
        currency = str(raw.get("currency") or "USD")[:8]
        org = raw.get("org") or {}
        org_name = org.get("name") or org.get("domain")

        txns: list[NormTxn] = []
        for t in raw.get("transactions", []) or []:
            posted = _epoch_to_dt(t.get("posted")) or _epoch_to_dt(t.get("transacted_at"))
            amount = _to_minor(t.get("amount"), currency)
            if posted is None or amount is None or not t.get("id"):
                continue  # drop malformed rows rather than corrupt the ledger
            txns.append(
                NormTxn(
                    external_id=str(t["id"]),
                    posted_at=posted,
                    amount_minor=amount,
                    description=str(t.get("description") or "")[:2000],
                    payee=(str(t["payee"])[:255] if t.get("payee") else None),
                    memo=(str(t["memo"])[:2000] if t.get("memo") else None),
                    pending=bool(t.get("pending", False)),
                )
            )

        holdings: list[NormHolding] = []
        for h in raw.get("holdings", []) or []:
            if not h.get("id"):
                continue
            hcur = str(h.get("currency") or currency)[:8]
            holdings.append(
                NormHolding(
                    external_id=str(h["id"]),
                    symbol=(str(h["symbol"])[:32] if h.get("symbol") else None),
                    description=(str(h["description"])[:255] if h.get("description") else None),
                    shares=(str(h["shares"]) if h.get("shares") is not None else None),
                    market_value_minor=_to_minor(h.get("market_value"), hcur),
                    cost_basis_minor=_to_minor(h.get("cost_basis"), hcur),
                    currency=hcur,
                    as_of=_epoch_to_dt(h.get("created")),
                )
            )

        if not raw.get("id"):
            continue
        accounts.append(
            NormAccount(
                external_id=str(raw["id"]),
                org_name=(str(org_name)[:255] if org_name else None),
                name=str(raw.get("name") or "Account")[:255],
                currency=currency,
                balance_minor=_to_minor(raw.get("balance"), currency) or 0,
                available_minor=_to_minor(raw.get("available-balance"), currency),
                balance_date=_epoch_to_dt(raw.get("balance-date")),
                transactions=txns,
                holdings=holdings,
            )
        )

    return SyncPayload(accounts=accounts, errors=errors)
