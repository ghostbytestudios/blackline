# Contributing to Blackline

Thanks for your interest! Blackline is a local-first, encrypted personal-finance
dashboard. Contributions of all sizes are welcome — bug reports, docs fixes,
tests, and features.

## Getting set up

You need Python 3.12+ (3.14 is what CI runs) and Node 20+.

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app          # runs on 127.0.0.1:8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                   # runs on 127.0.0.1:5173
```

Open http://127.0.0.1:5173, create a vault with any passphrase, and use
**Settings → Demo Mode** to load realistic fictional data — you don't need a
bank connection to develop.

## Running the checks

All of these must pass before a PR merges (CI runs them on every push):

```bash
cd backend && python -m ruff check . # backend lint
cd backend && python -m pytest       # backend test suite
cd frontend && npm run lint          # eslint (typescript + react-hooks rules)
cd frontend && npm run build         # TypeScript check + production build
```

Please add tests for any backend behavior change. Tests use a plain in-memory
SQLite database (see `backend/tests/conftest.py`) — they never touch a real
vault.

## Design principles (please keep these)

These aren't preferences; the app's security story depends on them:

- **Local-only.** The backend binds `127.0.0.1` and makes exactly one kind of
  outbound request (SimpleFIN sync). No telemetry, no analytics, no CDN assets,
  no other network calls — a contribution that adds one will be declined.
- **Encrypted at rest.** The database exists on disk only as an AES-256-GCM
  blob. Never write plaintext financial data to disk (including logs and
  temp files). The AAD constant in `security/crypto.py` must never change, or
  existing vaults become undecryptable.
- **Money is integer minor units (cents).** No floats in money math, anywhere.
- **Migrations must be defensive.** Fresh vaults are created with the full
  current schema and stamped at head, so migrations may run against databases
  that already have the columns/tables they add — always check existence first
  (see `backend/migrations/README.md`).
- **Sync never clobbers user data.** User-set categories, notes, tags, and
  account settings survive re-syncs.

## Pull requests

- Keep PRs focused on one change.
- Match the style around you (the codebase favors explanatory docstrings on
  modules and non-obvious logic, and comments that say *why*, not *what*).
- Describe what you changed and how you verified it.

## Reporting bugs

Open a GitHub issue with steps to reproduce. **Never include real financial
data, account identifiers, or your SimpleFIN token in an issue** — reproduce
with demo-mode data instead. For security vulnerabilities, see
[SECURITY.md](SECURITY.md) instead of opening a public issue.
