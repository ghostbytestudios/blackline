# Security Model & Threat Model

This app handles **highly sensitive financial data**. This document states what we
defend against, what we explicitly do *not*, and the controls in place.

## Assets

1. **SimpleFIN Access URL** — a bearer credential granting *read-only* access to your
   linked accounts. This is the crown jewel. If leaked, an attacker can read your
   transactions and balances (but cannot move money — SimpleFIN is read-only).
2. **Transaction & holdings history** — sensitive financial records stored locally.
3. **App passphrase** — unlocks the encrypted secret vault.

## Trust boundaries

- **Localhost only.** The HTTP server binds to `127.0.0.1`. It is never exposed to the
  LAN or internet. There is no remote login surface.
- **Single outbound egress.** The app makes outbound network requests to exactly one
  destination: the SimpleFIN Bridge host, and only during a user-initiated sync.
- **All other input is untrusted**, including data returned by SimpleFIN (validated/
  normalized before storage).

## Controls

| Control | Implementation |
|---|---|
| Network exposure | Bind `127.0.0.1`; CORS limited to the local Vite origin |
| **Whole-DB at rest** | Entire database encrypted with **AES-256-GCM**; persisted only as `vaultcfo.db.enc`. No plaintext DB file ever exists on disk. |
| Secret at rest | SimpleFIN access URL additionally encrypted as a secret within that DB |
| Key derivation | **Argon2id** from the app passphrase; per-install random salt |
| Key handling | Derived key kept in memory only while unlocked; zeroized on lock |
| DB in use | While unlocked the DB lives in an **in-memory** SQLite connection (`sqlite3.serialize/deserialize`); re-encrypted and rewritten atomically after every committed write |
| Wrong passphrase | Fails authenticated decryption of the DB blob — there is no oracle/plaintext check to attack |
| Setup token | Exchanged once, then discarded; never persisted |
| Read-only by design | SimpleFIN tokens cannot initiate payments |
| Input validation | All API inputs validated via Pydantic; SimpleFIN payloads normalized |
| SQL injection | SQLAlchemy parameterized queries only |
| Audit log | Every sync and secret operation is logged locally with timestamp |
| Dependency hygiene | Pinned versions; minimal dependency surface |
| Safe failure | Sync failures never partially corrupt state (transactional upserts) |

## Known gaps / tradeoffs (be honest)

- **Durability vs. crash window.** Because the DB lives in memory and is re-encrypted to
  disk after each committed write, a hard crash *between* a commit and its disk flush could
  lose the most recent write. For a single-user local app this window is tiny and
  acceptable; the encrypted blob is written atomically (temp + `os.replace`) so it is never
  left half-written/corrupt.
- **Whole DB in RAM while unlocked.** Fine for personal-finance data sizes (thousands of
  rows). Not intended for huge datasets.
- **SQLCipher note.** A page-level encrypted store (SQLCipher) would avoid holding the whole
  DB in memory, but has no prebuilt wheel for Python 3.14 on Windows. The serialize-based
  approach gives equivalent at-rest protection without a native build. Revisit if a wheel
  becomes available.
- **Memory exposure.** While unlocked, the derived key and decrypted access URL live in
  process memory. A local attacker with admin/debugger access could read them. This is
  inherent to any local app; full-disk encryption + OS account security are the defense.
- **No app-level rate limiting / brute force lockout on the passphrase yet.** Planned.

## What this app deliberately does NOT do

- Never stores or transmits bank usernames/passwords.
- Never screen-scrapes.
- Never sends your financial data to any third party other than the SimpleFIN Bridge
  *you* explicitly connected (and even then, only pulls — never pushes).
- Never opens a port beyond localhost.

## Reporting

This is a personal, self-hosted app. If you fork/extend it, keep the localhost binding
and the read-only integration posture intact.
