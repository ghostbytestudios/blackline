# Changelog

All notable changes to Blackline are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/) (0.x: minor bumps may include
breaking changes).

## [0.1.0] - 2026-07-09

Initial release: a private, local-first personal finance dashboard. Everything
runs on your own machine; the only outbound network call is the read-only
SimpleFIN sync you trigger yourself.

### Security & vault

- Whole-database encryption at rest: the DB exists on disk only as an
  AES-256-GCM blob, keyed from your passphrase via Argon2id. No plaintext
  database file is ever written.
- Unlock rate limiting (3 free attempts, then exponential backoff), automatic
  vault lock after idle minutes, and rotating encrypted backups before each sync.
- Vault reset flow for a forgotten passphrase (typed confirmation, destroys all
  data by design — there is no recovery).
- Localhost-only server with restrictive CORS and security headers; local
  audit log of syncs, unlocks, and secret operations.

### Accounts & data

- SimpleFIN sync: accounts, transactions, and investment holdings, idempotent
  across re-syncs; user edits (categories, notes, tags, account roles) are
  never clobbered.
- CSV/OFX/QFX statement import with automatic column-mapping suggestions,
  date/amount format detection, duplicate detection against synced data, and
  manual accounts for banks you don't link.
- CSV export (date-filtered) for spreadsheets and taxes.
- Automatic transaction categorization that learns rules from your corrections.
- In-app demo mode: a realistic six-month fictional household, added and
  removed with one click.
- Schema migrations run in-process at unlock — upgrading the app never needs a
  manual database step.

### Dashboard & insights

- Dark command-center dashboard: spent today/yesterday/month-to-date, a
  cumulative spend-pace chart versus last month, net worth, income, recurring
  total, budget status, savings-rate health, and recent activity on one screen.
- Recurring charge detection (fixed-price bills, subscriptions, loan payments —
  variable retail spending excluded) with upcoming-bills projection.
- 30-day cash-flow forecast built from detected bills, income, and average
  day-to-day spending on liquid accounts.
- Monthly budgets with optional month-to-month rollover and a six-month budget
  history grid; one-click 50/30/20 budget suggestions from your income.
- Multi-account savings goals with deadlines, required-per-month math, and
  on-track status.
- Merchant view: per-merchant totals and monthly averages.
- Investment holdings, allocation, per-holding gain/loss, and portfolio value
  history against cost basis.
- Historical net-worth tracking with daily snapshots.
- Insight cards: spending spikes, budget overruns, idle cash, and
  budgeting-ratio guidance.
- Transaction search, notes, and tags; guided first-run tutorial.

### Project

- 130-test backend suite; GitHub Actions CI (backend tests + frontend build)
  on every push and pull request.
- One-command start scripts for Windows (`start.ps1`) and macOS/Linux
  (`start.sh`) with first-run bootstrap.
- GPLv3 licensed, with contributor and security-reporting docs.

[0.1.0]: https://github.com/ghostbytestudios/blackline/releases/tag/v0.1.0
