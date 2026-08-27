#!/bin/bash
# Install the print agent as a launchd service (runs at login).
#
# The plist is GENERATED from com.labelprinter.print-agent.plist by substituting
# __PROJECT_DIR__ with this checkout's real location, so the installed job always
# points at wherever the repo currently lives. Never copy the template verbatim:
# hardcoded paths rot silently when the checkout moves (this job sat dead from
# 2026-01-26 to 2026-08-26 still pointing at ~/Documents/GitHub, and launchd
# reported only a bare exit 78).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.labelprinter.print-agent.plist"
PLIST_SRC="$PROJECT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LABEL="com.labelprinter.print-agent"

echo "Installing print agent service..."
echo "  project dir: $PROJECT_DIR"

[ -f "$PLIST_SRC" ] || { echo "ERROR: template not found: $PLIST_SRC" >&2; exit 1; }

# Preflight: launchd's exit 78 for a missing executable is nearly unreadable,
# so fail here with something actionable instead.
for required in "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/print_agent.py"; do
    if [ ! -e "$required" ]; then
        echo "ERROR: missing $required" >&2
        echo "       Run scripts/setup_venv.sh first, or check the checkout is complete." >&2
        exit 1
    fi
done

mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$(dirname "$PLIST_DST")"

# Stop the existing service before overwriting its plist.
if launchctl list | grep -q "$LABEL"; then
    echo "Stopping existing service..."
    launchctl bootout "gui/$UID/$LABEL" 2>/dev/null \
        || launchctl unload "$PLIST_DST" 2>/dev/null \
        || true
fi

# Generate the plist. Bash parameter expansion avoids sed delimiter trouble if
# PROJECT_DIR ever contains a '/' or '#'.
echo "Generating $PLIST_DST"
template="$(cat "$PLIST_SRC")"
printf '%s\n' "${template//__PROJECT_DIR__/$PROJECT_DIR}" > "$PLIST_DST"

# A malformed plist otherwise fails later as an opaque load error.
plutil -lint "$PLIST_DST" >/dev/null || { echo "ERROR: generated plist is invalid" >&2; exit 1; }

if grep -q '__PROJECT_DIR__' "$PLIST_DST"; then
    echo "ERROR: placeholder left unsubstituted in $PLIST_DST" >&2
    exit 1
fi

echo "Loading service..."
launchctl bootstrap "gui/$UID" "$PLIST_DST" 2>/dev/null \
    || launchctl load "$PLIST_DST"

echo ""
echo "Print agent installed and started!"
echo ""
echo "Useful commands:"
echo "  Check status:  launchctl list | grep print-agent"
echo "  View logs:     tail -f $PROJECT_DIR/logs/print-agent.log"
echo "  Stop service:  launchctl bootout gui/\$UID/$LABEL"
echo "  Start service: launchctl bootstrap gui/\$UID $PLIST_DST"
echo ""
echo "Test the agent:  curl http://127.0.0.1:5001/health"
