#!/usr/bin/env bash
set -euo pipefail

# Pin exact versions of core deps from the CURRENT Python env
# Produces requirements.lock alongside requirements.txt

here="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$here"

# Choose Python: prefer project venv, else system python3
PY="$here/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="${PYTHON_BIN:-python3}"
fi

echo "[pin] Using: $PY"

packages=(flask gunicorn pillow bleak)

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

for pkg in "${packages[@]}"; do
  ver=$($PY - <<'PY'
import sys
from importlib.metadata import version, PackageNotFoundError
name = sys.argv[1]
try:
    print(version(name))
except PackageNotFoundError:
    print("")
PY
"$pkg")
  if [ -n "$ver" ]; then
    echo "${pkg}==${ver}" >> "$tmpfile"
  else
    echo "[pin] WARNING: $pkg not found in this environment; skipping" >&2
  fi
done

mv "$tmpfile" requirements.lock
echo "[pin] Wrote $(wc -l < requirements.lock) entries to requirements.lock"

