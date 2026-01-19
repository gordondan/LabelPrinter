#!/bin/bash
# Install the print agent as a launchd service (runs at login)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.labelprinter.print-agent.plist"
PLIST_SRC="$PROJECT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Installing print agent service..."

# Create logs directory if needed
mkdir -p "$PROJECT_DIR/logs"

# Stop existing service if running
if launchctl list | grep -q "com.labelprinter.print-agent"; then
    echo "Stopping existing service..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Copy plist to LaunchAgents
echo "Copying plist to $PLIST_DST"
cp "$PLIST_SRC" "$PLIST_DST"

# Load the service
echo "Loading service..."
launchctl load "$PLIST_DST"

echo ""
echo "Print agent installed and started!"
echo ""
echo "Useful commands:"
echo "  Check status:  launchctl list | grep print-agent"
echo "  View logs:     tail -f $PROJECT_DIR/logs/print-agent.log"
echo "  Stop service:  launchctl unload $PLIST_DST"
echo "  Start service: launchctl load $PLIST_DST"
echo ""
echo "Test the agent:  curl http://127.0.0.1:5001/health"
