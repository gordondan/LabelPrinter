#!/bin/bash
# Watchdog script for LabelPrinter services
# Checks if Docker and the web app container are running, restarts if needed

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/watchdog.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Ensure log directory exists
mkdir -p "$PROJECT_DIR/logs"

# Check if Docker is running
if ! docker info &>/dev/null; then
    log "Docker is not running. Attempting to start Docker Desktop..."
    open -a Docker
    # Wait for Docker to start (up to 60 seconds)
    for i in {1..12}; do
        sleep 5
        if docker info &>/dev/null; then
            log "Docker started successfully after $((i * 5)) seconds"
            break
        fi
    done
    if ! docker info &>/dev/null; then
        log "ERROR: Failed to start Docker after 60 seconds"
        exit 1
    fi
fi

# Check if container exists and is running
CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' label-printer-app 2>/dev/null)

if [[ -z "$CONTAINER_STATUS" ]]; then
    log "Container does not exist. Starting with docker compose..."
    cd "$PROJECT_DIR"
    docker compose up -d
    log "Container started"
elif [[ "$CONTAINER_STATUS" != "running" ]]; then
    log "Container exists but status is '$CONTAINER_STATUS'. Restarting..."
    cd "$PROJECT_DIR"
    docker compose up -d
    log "Container restarted"
else
    # Container is running, check if it's healthy
    HEALTH_STATUS=$(docker inspect -f '{{.State.Health.Status}}' label-printer-app 2>/dev/null)

    if [[ "$HEALTH_STATUS" == "unhealthy" ]]; then
        log "Container is unhealthy. Restarting..."
        docker restart label-printer-app
        log "Container restarted due to unhealthy status"
    fi

    # Also do a quick HTTP check
    if ! curl -sf --max-time 5 http://localhost:3005/health &>/dev/null; then
        log "Health endpoint not responding. Restarting container..."
        docker restart label-printer-app
        log "Container restarted due to unresponsive health endpoint"
    fi
fi
