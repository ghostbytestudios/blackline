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
| Secret at rest | SimpleFIN access URL encrypted with **AES-256-GCM** |
| Key derivation | **Argon2id** from the app passphrase; per-install random salt |
| Key handling | Derived key kept in memory only while unlocked; zeroized on lock |
| Setup token | Exchanged once, then discarded; never persisted |
| Read-only by design | SimpleFIN tokens cannot initiate payments |
| Input validation | All API inputs validated via Pydantic; SimpleFIN payloads normalized |
| SQL injection | SQLAlchemy parameterized queries only |
| Audit log | Every sync and secret operation is logged locally with timestamp |
| Dependency hygiene | Pinned versions; minimal dependency surface |
| Safe failure | Sync failures never partially corrupt state (transactional upserts) |

## Known gaps / tradeoffs (be honest)

- **Full-DB encryption is NOT yet enabled.** The transaction database itself is plain
  SQLite. The *secret vault* (access URL) is encrypted, but transaction rows are not.
  **Mitigation today:** enable **BitLocker** (full-disk encryption) on Windows.
  **Upgrade path:** SQLCipher / SQLite encryption extension (deferred due to Python 3.14
  native-build friction on Windows).
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
