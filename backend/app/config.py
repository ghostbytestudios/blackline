"""Application configuration.

Settings are env-driven with safe, local-first defaults. The defaults alone are
sufficient to run securely on localhost; nothing here should ever widen network
exposure without an explicit, deliberate change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BLACKLINE_",
        extra="ignore",
    )

    # --- Storage ---
    data_dir: Path = Field(default=BACKEND_ROOT / "data")

    # --- Network (keep local!) ---
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_origin: str = "http://127.0.0.1:5173"

    # --- Outbound egress allowlist ---
    # Comma-separated exact hostnames the app may ever talk to. Both official
    # SimpleFIN bridge hosts by default; self-hosters add their own.
    simplefin_allowed_host: str = "bridge.simplefin.org,beta-bridge.simplefin.org"

    # --- Argon2id key-derivation parameters ---
    argon2_time_cost: int = 3
    argon2_memory_kib: int = 262_144  # 256 MiB
    argon2_parallelism: int = 4

    # --- Session & backups ---
    auto_lock_minutes: int = 15  # lock the vault after this many idle minutes (0 = never)
    backup_count: int = 5  # encrypted-blob backups to keep (0 = disable backups)

    @property
    def salt_path(self) -> Path:
        return self.data_dir / "vault.salt"

    @property
    def db_enc_path(self) -> Path:
        """Encrypted database blob (AES-256-GCM). The only on-disk form of the DB."""
        return self.data_dir / "blackline.db.enc"

    @property
    def backup_dir(self) -> Path:
        """Rotated copies of the encrypted blob (same ciphertext-only safety as the original)."""
        return self.data_dir / "backups"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def assert_local_only(self) -> None:
        """Fail loudly if someone tries to expose the app beyond localhost."""
        allowed = {"127.0.0.1", "localhost", "::1"}
        if self.host not in allowed:
            raise RuntimeError(
                f"Refusing to start: host={self.host!r} is not localhost. "
                "This app is local-only by design. Set BLACKLINE_HOST=127.0.0.1."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
