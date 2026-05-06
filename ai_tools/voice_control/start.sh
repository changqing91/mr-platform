#!/usr/bin/env bash
# start.sh — set up venv and launch the VRED Voice Control service
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "[voice_control] Creating Python virtual environment …"
    python3 -m venv "$VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Install / upgrade dependencies
echo "[voice_control] Installing dependencies …"
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Copy env file on first run
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "[voice_control] Creating .env from .env.example — please edit it before production use."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
fi

# Determine port from .env (default 8765)
PORT=$(grep -E '^SERVICE_PORT=' "$SCRIPT_DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
PORT=${PORT:-8765}

echo "[voice_control] Starting service on port $PORT …"
uvicorn server:app --host 0.0.0.0 --port "$PORT" --reload
