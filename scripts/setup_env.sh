#!/usr/bin/env bash
# Create a single env file for LabelPrinter that can be sourced by bash and read by systemd.
# Usage: sudo ./scripts/setup_env.sh
set -euo pipefail

ENV_FILE=/etc/default/labelprinter

# Default values (edit below as needed)
: "${GPIO_ENABLED:=1}"
: "${TODAY_BUTTON_PIN:=26}"
: "${TODAY_BUTTON_EDGE:=FALLING}"
: "${TODAY_BUTTON_PULL:=UP}"
: "${TODAY_BUTTON_BOUNCE_MS:=200}"
: "${TODAY_BUTTON_ACTION:=PRINT_TODAY}"

# Optional printing defaults
: "${LABEL_BORDER_ENABLED:=1}"
# Example: set a Windows printer name or default printer for Windows backend
: "${PRINTER_NAME:=}"

# Write env file atomically
TMP=$(mktemp)
cat >"$TMP" <<'EOF'
# LabelPrinter environment file (/etc/default/labelprinter)
# This file is used by systemd units and can also be sourced by your shell (~/.bashrc).
# To apply to systemd after changes:
#   sudo systemctl daemon-reload
#   sudo systemctl restart labelprinter.service
#   sudo systemctl restart labelprinter-tcp.service

# --- GPIO / Today Button ---
GPIO_ENABLED=${GPIO_ENABLED}
TODAY_BUTTON_PIN=${TODAY_BUTTON_PIN}
TODAY_BUTTON_EDGE=${TODAY_BUTTON_EDGE}
TODAY_BUTTON_PULL=${TODAY_BUTTON_PULL}
TODAY_BUTTON_BOUNCE_MS=${TODAY_BUTTON_BOUNCE_MS}
TODAY_BUTTON_ACTION=${TODAY_BUTTON_ACTION}

# --- Printing defaults ---
LABEL_BORDER_ENABLED=${LABEL_BORDER_ENABLED}
# PRINTER_NAME=${PRINTER_NAME}
EOF
sudo install -m 0644 "$TMP" "$ENV_FILE"
rm -f "$TMP"

echo "Wrote $ENV_FILE"

# Optionally append to the invoking user's ~/.bashrc if not already present
BASHRC="$HOME/.bashrc"
LINE='[ -f /etc/default/labelprinter ] && . /etc/default/labelprinter'
if ! grep -Fq "$LINE" "$BASHRC" 2>/dev/null; then
  echo "$LINE" >> "$BASHRC"
  echo "Appended source line to $BASHRC"
fi

echo "Done. Remember to reload systemd and restart services to pick up changes."
