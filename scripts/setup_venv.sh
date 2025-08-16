#!/usr/bin/env bash
set -euo pipefail

# Simple setup script for LabelPrinter Python environment
# - Creates a venv at .venv
# - Upgrades pip
# - Installs required packages

here="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$here"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[setup] Using python: $PYTHON_BIN"

if [ ! -d .venv ]; then
  echo "[setup] Creating virtualenv at .venv"
  "$PYTHON_BIN" -m venv .venv
fi

echo "[setup] Upgrading pip/wheel"
"$here/.venv/bin/python" -m pip install --upgrade pip wheel

echo "[setup] Installing dependencies: flask gunicorn pillow bleak"
"$here/.venv/bin/pip" install flask gunicorn pillow bleak

echo "[setup] Done. Activate with: source .venv/bin/activate"
echo "[setup] Run dev server:   python server.py"
echo "[setup] Run gunicorn:     .venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 server:app"

