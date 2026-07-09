"""Shared pytest fixtures.

Env overrides are set *before* any `app` import so `get_settings()` (lru_cached)
picks them up: fast Argon2 parameters (the production 256 MiB / 3-pass setting
would make every key-derivation test take ~1s) — security margins are irrelevant
for throwaway test vaults.
"""

from __future__ import annotations

import os

os.environ["BLACKLINE_ARGON2_TIME_COST"] = "1"
os.environ["BLACKLINE_ARGON2_MEMORY_KIB"] = "8192"
os.environ["BLACKLINE_ARGON2_PARALLELISM"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401  (register tables on Base.metadata)


@pytest.fixture()
def db() -> Session:
    """Plain in-memory SQLite session with the full schema — no encryption layer.

    Services take a Session, so most logic tests don't need the encrypted-blob
    machinery at all.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Point the app's data dir (blob, salt, backups) at a throwaway directory."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("BLACKLINE_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    yield data_dir
    get_settings.cache_clear()
