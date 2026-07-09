"""FastAPI application entrypoint.

Local-only by design: binds 127.0.0.1, restricts CORS to the local frontend origin,
and adds defensive security headers. The vault starts locked.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from . import audit
from .config import get_settings
from .db import DatabaseLocked, read_scope
from .routers import (
    accounts,
    auth,
    budgets,
    connect,
    demo,
    goals,
    imports,
    insights,
    profile,
    transactions,
)
from .security.lock import app_lock

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # The DB is encrypted and only opens on unlock, so nothing DB-related happens here.
    settings.assert_local_only()
    settings.ensure_dirs()
    yield


app = FastAPI(
    title="Blackline",
    description="Local-only personal finance dashboard.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: only the local Vite dev origin may call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


# Requests to these paths don't count as user activity: the frontend polls/refetches
# them passively (e.g. on window focus), and a focused-but-idle window should not keep
# the vault unlocked forever.
_PASSIVE_PATHS = {"/health", "/api/status"}


@app.middleware("http")
async def auto_lock(request: Request, call_next) -> Response:
    if app_lock.should_auto_lock():
        # Audit while the DB is still open; locking closes it.
        with read_scope() as db:
            audit.record(db, "auto_lock", detail=f"idle>{settings.auto_lock_minutes}m")
        app_lock.lock()
    elif request.method != "OPTIONS" and request.url.path not in _PASSIVE_PATHS:
        app_lock.touch()
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(DatabaseLocked)
async def _locked_handler(_request: Request, _exc: DatabaseLocked) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_423_LOCKED,
        content={"detail": "Application is locked. Unlock with your passphrase."},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


for r in (
    auth.router,
    connect.router,
    accounts.router,
    transactions.router,
    insights.router,
    budgets.router,
    profile.router,
    demo.router,
    goals.router,
    imports.router,
):
    app.include_router(r, prefix="/api")


def main() -> None:
    import uvicorn

    settings.assert_local_only()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
