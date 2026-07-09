#!/usr/bin/env bash
# Launches Blackline: backend (FastAPI on 127.0.0.1:8000) in the background,
# frontend (Vite on 127.0.0.1:5173) in the foreground. First run bootstraps
# the Python venv and npm packages automatically. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"

# --- Backend bootstrap -------------------------------------------------------
if [ ! -e backend/.venv/bin/python ]; then
    echo "First run: creating Python venv and installing backend dependencies..."
    python3 -m venv backend/.venv
    backend/.venv/bin/python -m pip install --quiet -r backend/requirements.txt
fi

# --- Frontend bootstrap ------------------------------------------------------
if [ ! -d frontend/node_modules ]; then
    echo "First run: installing frontend dependencies..."
    (cd frontend && npm install)
fi

# --- Launch ------------------------------------------------------------------
echo "Starting backend on http://127.0.0.1:8000 ..."
(cd backend && exec .venv/bin/python -m uvicorn app.main:app) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null' EXIT

echo "Starting frontend on http://127.0.0.1:5173 (Ctrl+C stops both)..."
cd frontend && npm run dev
