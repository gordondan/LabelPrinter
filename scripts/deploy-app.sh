#!/bin/bash
# Install LabelPrinter services on macOS
# - Print Agent: runs at boot as root (for USB access)
# - Web App: runs at login via Docker
#
# Usage:
#   ./install-macos-services.sh        # Rebuild Docker image + deploy
#   ./install-macos-services.sh --fast # Skip rebuild, just restart services

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
REBUILD=true
for arg in "$@"; do
    case $arg in
        --fast)
            REBUILD=false
            shift
            ;;
    esac
done

DAEMON_PLIST="com.labelprinter.print-agent-daemon.plist"
AGENT_PLIST="com.labelprinter.web-app.plist"
WATCHDOG_PLIST="com.labelprinter.watchdog.plist"

DAEMON_SRC="$PROJECT_DIR/$DAEMON_PLIST"
AGENT_SRC="$PROJECT_DIR/$AGENT_PLIST"
WATCHDOG_SRC="$PROJECT_DIR/$WATCHDOG_PLIST"

DAEMON_DST="/Library/LaunchDaemons/com.labelprinter.print-agent.plist"
AGENT_DST="$HOME/Library/LaunchAgents/$AGENT_PLIST"
WATCHDOG_DST="$HOME/Library/LaunchAgents/$WATCHDOG_PLIST"

echo "========================================"
echo "LabelPrinter macOS Services Installer"
echo "========================================"
if [[ "$REBUILD" == true ]]; then
    echo "Mode: Rebuild + Deploy (use --fast to skip rebuild)"
else
    echo "Mode: Fast Deploy (skipping Docker rebuild)"
fi
echo ""

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Check if running with sudo for daemon installation
if [[ $EUID -ne 0 ]]; then
    echo "This script needs sudo to install the print agent daemon."
    echo "Re-running with sudo..."
    exec sudo "$0" "$@"
fi

# Get the actual user (not root when running under sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo "~$ACTUAL_USER")
AGENT_DST="$ACTUAL_HOME/Library/LaunchAgents/$AGENT_PLIST"

echo "[1/4] Installing Print Agent (LaunchDaemon)..."
echo "      This runs at boot as root for USB access"

# Stop existing daemon if running
if launchctl list 2>/dev/null | grep -q "com.labelprinter.print-agent"; then
    echo "      Stopping existing launchd service..."
    launchctl bootout system/com.labelprinter.print-agent 2>/dev/null || true
fi

# Kill any process using port 5001 (print agent port)
PORT_5001_PID=$(lsof -ti :5001 2>/dev/null || true)
if [[ -n "$PORT_5001_PID" ]]; then
    echo "      Killing existing process on port 5001 (PID: $PORT_5001_PID)..."
    kill -9 $PORT_5001_PID 2>/dev/null || true
    sleep 1
fi

# Copy and load daemon
cp "$DAEMON_SRC" "$DAEMON_DST"
chmod 644 "$DAEMON_DST"
chown root:wheel "$DAEMON_DST"
launchctl bootstrap system "$DAEMON_DST"

echo "      ✓ Print Agent daemon installed"
echo ""

echo "[2/4] Installing Web App (LaunchAgent)..."
echo "      This runs at login to start the Docker container"

# Create LaunchAgents directory if needed
mkdir -p "$ACTUAL_HOME/Library/LaunchAgents"

# Stop existing agent if running (as the actual user)
sudo -u "$ACTUAL_USER" launchctl bootout "gui/$(id -u $ACTUAL_USER)/com.labelprinter.web-app" 2>/dev/null || true

# Stop existing Docker container if running
if docker ps -q -f name=label-printer-app 2>/dev/null | grep -q .; then
    echo "      Stopping existing Docker container..."
    docker stop label-printer-app 2>/dev/null || true
    docker rm label-printer-app 2>/dev/null || true
fi

# Kill any non-Docker process using port 3005
PORT_3005_PID=$(lsof -ti :3005 2>/dev/null || true)
if [[ -n "$PORT_3005_PID" ]]; then
    echo "      Killing existing process on port 3005 (PID: $PORT_3005_PID)..."
    kill -9 $PORT_3005_PID 2>/dev/null || true
    sleep 1
fi

# Copy and load agent (owned by user)
cp "$AGENT_SRC" "$AGENT_DST"
chmod 644 "$AGENT_DST"
chown "$ACTUAL_USER" "$AGENT_DST"
sudo -u "$ACTUAL_USER" launchctl bootstrap "gui/$(id -u $ACTUAL_USER)" "$AGENT_DST"

echo "      ✓ Web App agent installed"

# Rebuild Docker image if requested
if [[ "$REBUILD" == true ]]; then
    echo "      Rebuilding Docker image..."
    sudo -u "$ACTUAL_USER" docker compose -f "$PROJECT_DIR/docker-compose.yml" build
    echo "      ✓ Docker image rebuilt"
fi

# Start the Docker container now (don't wait for next login)
echo "      Starting Docker container..."
sudo -u "$ACTUAL_USER" docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d

echo "      ✓ Docker container started"
echo ""

echo "[3/5] Installing Watchdog service..."
echo "      This checks every 5 minutes and restarts if needed"

# Make watchdog script executable
chmod +x "$PROJECT_DIR/scripts/watchdog.sh"

# Stop existing watchdog if running
sudo -u "$ACTUAL_USER" launchctl bootout "gui/$(id -u $ACTUAL_USER)/com.labelprinter.watchdog" 2>/dev/null || true

# Copy and load watchdog agent
cp "$WATCHDOG_SRC" "$WATCHDOG_DST"
chmod 644 "$WATCHDOG_DST"
chown "$ACTUAL_USER" "$WATCHDOG_DST"
sudo -u "$ACTUAL_USER" launchctl bootstrap "gui/$(id -u $ACTUAL_USER)" "$WATCHDOG_DST"

echo "      ✓ Watchdog service installed"
echo ""

echo "[4/5] Verifying services..."
echo ""

# Check print agent
if launchctl print system/com.labelprinter.print-agent &>/dev/null; then
    echo "      ✓ Print Agent is running"
else
    echo "      ⚠ Print Agent may need a reboot to start"
fi

# Check web app agent
if sudo -u "$ACTUAL_USER" launchctl print "gui/$(id -u $ACTUAL_USER)/com.labelprinter.web-app" &>/dev/null; then
    echo "      ✓ Web App agent is loaded"
else
    echo "      ⚠ Web App agent may need re-login to start"
fi

# Check watchdog
if sudo -u "$ACTUAL_USER" launchctl print "gui/$(id -u $ACTUAL_USER)/com.labelprinter.watchdog" &>/dev/null; then
    echo "      ✓ Watchdog service is running"
else
    echo "      ⚠ Watchdog may need re-login to start"
fi

echo ""
echo "[5/5] Docker Desktop Configuration"
echo ""
echo "      IMPORTANT: Ensure Docker Desktop is set to start at login:"
echo "      Docker Desktop → Settings → General → Start Docker Desktop when you sign in"
echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Services installed:"
echo "  • Print Agent (port 5001) - runs at boot as root"
echo "  • Web App (port 3005)     - Docker container, starts at login"
echo "  • Watchdog                - checks every 5 min, restarts if needed"
echo ""
echo "Useful commands:"
echo "  Check print agent:    sudo launchctl print system/com.labelprinter.print-agent"
echo "  Check web app:        launchctl print gui/\$(id -u)/com.labelprinter.web-app"
echo "  Check watchdog:       launchctl print gui/\$(id -u)/com.labelprinter.watchdog"
echo "  View print agent log: tail -f $PROJECT_DIR/logs/print-agent.log"
echo "  View web app log:     tail -f $PROJECT_DIR/logs/docker-web-app.log"
echo "  View watchdog log:    tail -f $PROJECT_DIR/logs/watchdog.log"
echo ""
echo "To uninstall:"
echo "  sudo launchctl bootout system/com.labelprinter.print-agent"
echo "  launchctl bootout gui/\$(id -u)/com.labelprinter.web-app"
echo "  launchctl bootout gui/\$(id -u)/com.labelprinter.watchdog"
echo "  sudo rm $DAEMON_DST"
echo "  rm $AGENT_DST $WATCHDOG_DST"
echo ""
