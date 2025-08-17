# LabelPrinter Server — Running with Gunicorn and systemd

This repo includes a small Flask app in `server.py` that exposes HTTP endpoints to run `pi-label-printer.py` with various options. This guide shows how to:
- Run the server locally for testing
- Run it in production with Gunicorn
- Install it as a systemd service

## Endpoints
- `GET /app/pi-label` — Simple HTML form UI
- `GET /app/pi-label/options` — JSON of supported CLI flags for `pi-label-printer.py`
- `POST /app/pi-label/print` — Executes `pi-label-printer.py` with the provided JSON payload

## Prerequisites
- Python 3.9+
- A configured `printer-config.json` in the project root (copy from `printer-config.json.example` and adjust for your printer)
- For BLE printing (RW402B): system BlueZ stack, and network/Bluetooth permissions as appropriate

## Setup
1) Create and activate a virtual environment
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel
```

2) Install Python dependencies
Option A — via requirements.txt
```
pip install -r requirements.txt
```
Option B — install explicitly
```
pip install flask gunicorn pillow bleak
```
- `flask` — web framework serving the endpoints
- `gunicorn` — production WSGI server
- `pillow` — image processing used by the label generator
- `bleak` — BLE support used by `rw402b_ble` when printing to RW402B

### Pin to Current Environment (optional)
If you want to deploy with exact versions from your current environment, generate a lock file:
```
bash scripts/pin_requirements.sh
pip install -r requirements.lock
```
This writes `requirements.lock` with pinned versions for Flask, Gunicorn, Pillow, and Bleak.

### One‑liner: venv + install + pin
Run this to create a venv, install deps from `requirements.txt`, then pin exact versions into `requirements.lock`:
```
python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip wheel && pip install -r requirements.txt && bash scripts/pin_requirements.sh
```

3) Configure your printer
- Copy `printer-config.json.example` to `printer-config.json`
- Edit values (printer name, BLE device name, fonts, dimensions, etc.)

## Local Test (Dev Server)
Run the Flask dev server directly:
```
python server.py
```
Visit:
```
http://localhost:5000/app/pi-label
```

## Production Run with Gunicorn
From the project root (with the venv active):
```
cd /path/to/LabelPrinter
. .venv/bin/activate
exec gunicorn -w 2 -b 0.0.0.0:8000 server:app
```
Notes:
- `server:app` points Gunicorn to the Flask app object named `app` inside `server.py`.
- Adjust `-w` (workers) and `-b` (bind address/port) to match your host.

### Optional: Unix Socket bind
If you plan to reverse proxy with Nginx:
```
exec gunicorn -w 2 -b unix:/run/labelprinter/labelprinter.sock server:app
```
Ensure the socket directory exists and permissions allow your proxy user to read/write.

## Install as a systemd Service (recommended)
Create a unit file at `/etc/systemd/system/labelprinter.service`:
```
[Unit]
Description=LabelPrinter Gunicorn Service
After=network.target

[Service]
Type=simple
# Set these paths for your environment
WorkingDirectory=/path/to/LabelPrinter
Environment="PATH=/path/to/LabelPrinter/.venv/bin"
# Optional: pass Flask env or other config
# Environment="FLASK_ENV=production"

# Choose one ExecStart:
# 1) TCP port
ExecStart=/path/to/LabelPrinter/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 server:app
# 2) Unix socket (for Nginx)
# ExecStart=/path/to/LabelPrinter/.venv/bin/gunicorn -w 2 -b unix:/run/labelprinter/labelprinter.sock server:app

# Run as a non-root user that has access to the printer/BLE device
User=labelprinter
Group=labelprinter
Restart=on-failure
RestartSec=3

# If using a Unix socket, create and own the runtime dir
# RuntimeDirectory=labelprinter
# UMask=0007

[Install]
WantedBy=multi-user.target
```

Reload and start:
```
sudo systemctl daemon-reload
sudo systemctl enable --now labelprinter.service
sudo systemctl status labelprinter.service
```

View logs:
```
sudo journalctl -u labelprinter.service -e -f
```

### TCP variant service
If you prefer exposing a TCP port directly (no Unix socket/Nginx), a ready unit is included:

```
sudo cp systemd/labelprinter-tcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now labelprinter-tcp.service
sudo systemctl status labelprinter-tcp.service
```
This binds on `0.0.0.0:8000`. Adjust firewall rules or bind address as needed.

### Nginx (optional)
If you bind Gunicorn to a Unix socket, configure Nginx to proxy to it. Ensure the Nginx worker user can access the socket (matching `User`/`Group` or via `UMask`). The repo includes an `nginx/` directory you can adapt.

## Troubleshooting
- Permission errors for BLE/USB printing: run the service as a user in the appropriate groups (e.g., `lp`, `lpadmin`, `bluetooth`).
- `printer-config.json` missing/invalid: the print endpoint returns an error and underlying script will exit non‑zero.
- PIL/Pillow font path errors: double‑check `font_path` in `printer-config.json` exists on the host.
- Socket not created with Unix bind: ensure `RuntimeDirectory` or the parent dir exists and service has permission to create files there.

## Quick Reference
- Dev: `python server.py` (port 5000)
- Gunicorn (port 8000): `gunicorn -w 2 -b 0.0.0.0:8000 server:app`
- Form UI: `/app/pi-label`
- Print API: `POST /app/pi-label/print`

## Tailored systemd Unit (this repo path)
Use this unit with your current repo path and a Unix socket suitable for Nginx.

Path assumptions:
- Project: `/home/relay-admin/repo/LabelPrinter`
- Virtualenv: `/home/relay-admin/repo/LabelPrinter/.venv`

Create `/etc/systemd/system/labelprinter.service`:
```
[Unit]
Description=LabelPrinter Gunicorn Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/relay-admin/repo/LabelPrinter
Environment="PATH=/home/relay-admin/repo/LabelPrinter/.venv/bin"
Environment="PYTHONUNBUFFERED=1"

# Bind to Unix socket for Nginx
ExecStart=/home/relay-admin/repo/LabelPrinter/.venv/bin/gunicorn -w 2 -b unix:/run/labelprinter/labelprinter.sock server:app

# Run as your user; group www-data so Nginx can read the socket
User=relay-admin
Group=www-data
SupplementaryGroups=lp,bluetooth

# Manage /run/labelprinter and socket perms
RuntimeDirectory=labelprinter
RuntimeDirectoryMode=0775
UMask=0007

Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:
```
sudo systemctl daemon-reload
sudo systemctl enable --now labelprinter.service
sudo systemctl status labelprinter.service
```

Notes:
- Ensure the venv exists and has deps installed: `python3 -m venv .venv && . .venv/bin/activate && pip install flask gunicorn pillow bleak`.
- The service runs as `relay-admin` and belongs to groups `lp` and `bluetooth` for printer/BLE access. Adjust as needed.

## Nginx Snippet (Unix socket)
Example server block to proxy `/app/…` to the Gunicorn socket at `/run/labelprinter/labelprinter.sock`.

```
server {
    listen 80;
    server_name _;

    # Optional: increase if large responses
    client_max_body_size 4m;

    location /app/ {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://unix:/run/labelprinter/labelprinter.sock:/;
        proxy_redirect off;
    }
}
```

Permissions tip: because the service sets `Group=www-data`, the runtime dir `/run/labelprinter` gets group ownership that matches Nginx, and `UMask=0007` with `RuntimeDirectoryMode=0775` allows Nginx to access the socket without extra changes.

## tmpfiles.d (optional)
Systemd already creates `/run/labelprinter` at service start via `RuntimeDirectory=labelprinter`. If you also want the directory present early in boot (before the service starts), install the provided tmpfiles.d entry.

1) Review and copy the example:
```
cat tmpfiles.d/labelprinter.conf
sudo cp tmpfiles.d/labelprinter.conf /etc/tmpfiles.d/labelprinter.conf
```

2) Create the directory immediately and on next boots:
```
sudo systemd-tmpfiles --create /etc/tmpfiles.d/labelprinter.conf
```

This will ensure `/run/labelprinter` exists with mode `0775` and ownership `relay-admin:www-data` prior to the service starting.
