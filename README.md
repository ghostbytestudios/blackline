# VaultCFO — Local Personal Finance Dashboard

A **local-only** personal finance dashboard. It aggregates your bank and investment
accounts via [SimpleFIN Bridge](https://www.simplefin.org/) (read-only, consent-based),
stores everything on your own machine, and gives you spending insights and trends.

## Design principles

- **Local-first.** The server binds to `127.0.0.1` only. Nothing is exposed to your network.
- **Internet only on sync.** The *only* outbound network call is to the SimpleFIN
  Bridge during an explicit, user-initiated sync. Otherwise the app is fully offline.
- **No credential sharing, no scraping.** SimpleFIN gives a **read-only** access token.
  We never see, store, or transmit your bank username/password.
- **Whole database encrypted at rest.** The entire database is stored only as an
  AES-256-GCM-encrypted blob (`vaultcfo.db.enc`), keyed from your app passphrase
  (Argon2id). While unlocked it lives in memory; no plaintext DB ever hits disk.
  See [SECURITY.md](./SECURITY.md).

## Architecture

```
frontend/   React + Vite dashboard (talks only to localhost backend)
backend/    FastAPI app
  app/
    config.py            settings (env-driven, safe defaults)
    db.py                SQLAlchemy engine/session (local SQLite)
    models.py            ORM: accounts, transactions, holdings, secrets, audit
    schemas.py           Pydantic API contracts
    security/            crypto, key derivation, secret vault, app lock
    integrations/        SimpleFIN Bridge client (the only network egress)
    services/            sync, categorization, insights
    routers/             HTTP API
    main.py              app wiring, 127.0.0.1 bind, audit middleware
```

## Quick start (backend)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then edit .env and set a strong APP_PASSPHRASE_* policy
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API docs (local only): http://127.0.0.1:8000/docs

## Quick start (frontend)

Requires Node 20+ (https://nodejs.org).

```powershell
cd frontend
npm install
npm run dev
```

## Connecting an account (SimpleFIN)

1. Go to https://bridge.simplefin.org/, connect your bank(s), and create a **Setup Token**.
2. In the app: **Settings → Connect → paste Setup Token**. The app exchanges it once for a
   read-only Access URL, encrypts it, and discards the setup token.
3. Click **Sync**. Accounts, balances, and transactions are pulled and stored locally.

## Status

Early foundation. See the in-repo TODOs and `SECURITY.md` for the threat model.
