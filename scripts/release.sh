#!/usr/bin/env bash
set -euo pipefail

# Release helper for LabelPrinter
# - Commits current repo changes
# - Backs up existing deployment at /opt/LabelPrinter
# - Rsyncs pi-label-printer related files to the deployment directory

DEST_DIR="/opt/LabelPrinter"
BACKUP_ROOT="/opt/LabelPrinter-backups"
COMMIT_MSG="Release to /opt/LabelPrinter"
DRY_RUN=false

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  -d, --dest DIR        Destination directory (default: /opt/LabelPrinter)
  -b, --backups DIR     Backups root directory (default: /opt/LabelPrinter-backups)
  -m, --message MSG     Git commit message (default: "${COMMIT_MSG}")
  -n, --dry-run         Show actions without making changes
  -h, --help            Show this help

Notes:
  - Will use sudo as needed for /opt operations.
  - Only syncs a curated list of related files.
USAGE
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Error: '$1' not found in PATH" >&2; exit 1; }
}

# Parse args
while [[ ${1:-} ]]; do
  case "$1" in
    -d|--dest) DEST_DIR="$2"; shift 2;;
    -b|--backups) BACKUP_ROOT="$2"; shift 2;;
    -m|--message) COMMIT_MSG="$2"; shift 2;;
    -n|--dry-run) DRY_RUN=true; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 2;;
  esac
done

require_cmd git
require_cmd rsync
require_cmd date

# Determine repo root based on script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -d .git ]]; then
  echo "Error: This does not look like a git repository: $REPO_ROOT" >&2
  exit 1
fi

# Curated list of files and directories to deploy
# Adjust as needed for your environment.
FILES_TO_SYNC=(
  "pi-label-printer.py"
  "logger.py"
  "config.py"
  "rw402b_ble"
  "label-images"
  "printer-config.json"
  "printer-config.json.example"
  "requirements.txt"
  "find_rw402b.py"
  "server.py"
)

timestamp() { date +%Y%m%d-%H%M%S; }

maybe_sudo() {
  # Use sudo for /opt operations if current user lacks write perms
  local probe="$1"
  shift
  if [[ -w "$probe" ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

echo "[1/3] Committing repository changes..."
# Stage everything and commit only if there are changes
git add -A
if git diff --cached --quiet && git diff --quiet; then
  echo "No changes detected; skipping commit."
else
  if $DRY_RUN; then
    echo "DRY-RUN: Would commit changes with message: $COMMIT_MSG ($(timestamp))"
  else
    git commit -m "$COMMIT_MSG ($(timestamp))"
  fi
fi

echo "[2/3] Backing up existing deployment at $DEST_DIR..."
TS="$(timestamp)"
BACKUP_DIR="$BACKUP_ROOT/$TS"

if $DRY_RUN; then
  echo "DRY-RUN: Would create backup directory: $BACKUP_DIR"
  echo "DRY-RUN: Would archive $DEST_DIR -> $BACKUP_DIR/LabelPrinter.tgz"
else
  maybe_sudo "/opt" mkdir -p "$BACKUP_DIR"
  if maybe_sudo "$DEST_DIR" test -d "$DEST_DIR"; then
    # Create a tar.gz snapshot inside the backup folder
    echo "Creating backup archive..."
    maybe_sudo "$BACKUP_DIR" tar -czf "$BACKUP_DIR/LabelPrinter.tgz" -C "$(dirname "$DEST_DIR")" "$(basename "$DEST_DIR")"
    echo "Backup created: $BACKUP_DIR/LabelPrinter.tgz"
  else
    echo "Notice: Destination $DEST_DIR does not exist; skipping backup."
  fi
fi

echo "[3/3] Syncing selected files to $DEST_DIR..."
RSYNC_OPTS=(-av --delete --exclude "__pycache__/" --exclude ".venv/" --exclude ".git/" --exclude "logs/")
if $DRY_RUN; then
  RSYNC_OPTS+=(--dry-run)
fi

if ! $DRY_RUN; then
  maybe_sudo "/opt" mkdir -p "$DEST_DIR"
fi

SYNCED=()
for item in "${FILES_TO_SYNC[@]}"; do
  if [[ -e "$REPO_ROOT/$item" ]]; then
    echo "- Syncing $item"
    if $DRY_RUN; then
      rsync "${RSYNC_OPTS[@]}" "$REPO_ROOT/$item" "$DEST_DIR/"
    else
      maybe_sudo "$DEST_DIR" rsync "${RSYNC_OPTS[@]}" "$REPO_ROOT/$item" "$DEST_DIR/"
    fi
    SYNCED+=("$item")
  else
    echo "Warning: $item not found in repo; skipping"
  fi
done

echo "\nRelease complete. Summary:"
echo "- Destination: $DEST_DIR"
if [[ -f "$BACKUP_DIR/LabelPrinter.tgz" ]]; then
  echo "- Backup: $BACKUP_DIR/LabelPrinter.tgz"
else
  echo "- Backup: (none created)"
fi
echo "- Files synced: ${#SYNCED[@]}"
for s in "${SYNCED[@]}"; do echo "  * $s"; done

echo "\nTip: To test without changes, use: $0 --dry-run"
