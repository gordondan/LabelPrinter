#!/usr/bin/env python3
"""
Print Agent - A minimal service that bridges HTTP requests to USB/BLE printer.

Runs natively on Mac (not in Docker) to access USB/Bluetooth hardware.
Accepts print requests from Docker container via HTTP.

Usage:
    python print_agent.py

Listens on localhost:5001 (not exposed to network).
"""

import base64
import io
import json
import os
import sys
from pathlib import Path

from flask import Flask, request, jsonify

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

# Try USB first (faster, more reliable), fall back to BLE
USB_AVAILABLE = False
BLE_AVAILABLE = False

try:
    from rw402b_ble.usb_printer import RW402BUSBPrinter
    USB_AVAILABLE = True
except ImportError:
    pass

try:
    from rw402b_ble.linux.printer import RW402BPrinter
    BLE_AVAILABLE = True
except ImportError:
    pass

app = Flask(__name__)

# Load configuration
CONFIG_PATH = PROJECT_ROOT / "config" / "printer-config-macos.json"
if not CONFIG_PATH.exists():
    CONFIG_PATH = PROJECT_ROOT / "config" / "printer-config-linux.json"

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "print-agent"})

@app.route('/print', methods=['POST'])
def print_label():
    """
    Accept a print job and send to BLE printer.

    Request JSON:
        image_base64: base64-encoded PNG image data
        printer_name: optional printer name (default: from config)
        copies: number of copies (default: 1)

    Response JSON:
        ok: true/false
        message: status message
        error: error message if failed
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No JSON data provided"}), 400

        image_base64 = data.get('image_base64')
        if not image_base64:
            return jsonify({"ok": False, "error": "No image_base64 provided"}), 400

        printer_name = data.get('printer_name')
        copies = int(data.get('copies', 1))

        # Load config
        config = load_config()

        # Get printer config
        if not printer_name:
            printer_name = config.get('default_printer', 'RW402B')

        printer_cfg = config.get('printers', {}).get(printer_name)
        if not printer_cfg:
            return jsonify({"ok": False, "error": f"Printer '{printer_name}' not found in config"}), 400

        # Decode image
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            return jsonify({"ok": False, "error": f"Failed to decode image: {e}"}), 400

        # Create printer instance - prefer USB over BLE, with fallback
        use_usb = printer_cfg.get('use_usb', True) and USB_AVAILABLE
        printer = None
        print_method = None
        usb_error = None

        if use_usb:
            try:
                printer = RW402BUSBPrinter(
                    dpi=int(printer_cfg.get('dpi', 203)),
                    invert=bool(printer_cfg.get('invert', True))
                )
                # Test connection
                printer._connect()
                print_method = "USB"
            except Exception as e:
                usb_error = str(e)
                print(f"[print_agent] USB failed ({usb_error}), falling back to BLE")
                printer = None

        if printer is None and BLE_AVAILABLE:
            printer = RW402BPrinter(
                addr=printer_cfg.get('ble_mac'),
                timeout=float(printer_cfg.get('bluetooth_wait_time', 4.0)),
                dpi=int(printer_cfg.get('dpi', 203)),
                invert=bool(printer_cfg.get('invert', True)),
                prefer_resp=bool(printer_cfg.get('prefer_write_with_response', True)),
                chunk_size=int(printer_cfg.get('write_chunk_size', 20)),
                throttle_ms=int(printer_cfg.get('write_throttle_ms', 0))
            )
            print_method = "BLE"

        if printer is None:
            error_msg = f"No printer backend available. USB error: {usb_error}" if usb_error else "No printer backend available"
            return jsonify({"ok": False, "error": error_msg}), 500

        # Calculate label dimensions in mm. Prefer the actual image dimensions
        # (sent by the server based on the preview PNG) so the user-selected
        # label size reaches the printer's TSPL SIZE command. Fall back to the
        # printer config defaults when the request doesn't supply them.
        dpi_for_size = int(printer_cfg.get('dpi', 203))
        img_w_px = data.get('image_width_px')
        img_h_px = data.get('image_height_px')
        try:
            if img_w_px and img_h_px and dpi_for_size > 0:
                label_w_mm = (float(img_w_px) / dpi_for_size) * 25.4
                label_h_mm = (float(img_h_px) / dpi_for_size) * 25.4
            else:
                label_w_mm = float(printer_cfg.get('label_width_in', 3)) * 25.4
                label_h_mm = float(printer_cfg.get('label_height_in', 1)) * 25.4
        except (TypeError, ValueError):
            label_w_mm = float(printer_cfg.get('label_width_in', 3)) * 25.4
            label_h_mm = float(printer_cfg.get('label_height_in', 1)) * 25.4
        gap_mm = float(printer_cfg.get('gap_mm', 3.0))
        density = int(printer_cfg.get('density', 8))
        speed = int(printer_cfg.get('speed', 4))
        direction = int(printer_cfg.get('direction', 1))

        # Print the label(s)
        pause_between = float(config.get('pause_between_labels', 1))

        try:
            for i in range(copies):
                printer.print_pil_image(
                    image,
                    label_w_mm=label_w_mm,
                    label_h_mm=label_h_mm,
                    gap_mm=gap_mm,
                    density=density,
                    speed=speed,
                    direction=direction,
                    x=0, y=0, mode=0
                )

                if i < copies - 1 and pause_between > 0:
                    import time
                    time.sleep(pause_between)
        finally:
            # Always release USB resources to prevent "Access denied" on next request
            if hasattr(printer, 'close'):
                try:
                    printer.close()
                except Exception:
                    pass

        return jsonify({
            "ok": True,
            "message": f"Printed {copies} label(s) to {printer_name} via {print_method}"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/scan', methods=['GET'])
def scan_printers():
    """Scan for available BLE printers."""
    try:
        import asyncio
        from bleak import BleakScanner

        async def do_scan():
            devices = await BleakScanner.discover(timeout=4.0)
            printers = []
            for d in devices:
                name = d.name or ""
                if any(x in name.lower() for x in ['rw402b', 'munbyn', 'beeprt', 'printer']):
                    printers.append({
                        "address": d.address,
                        "name": d.name,
                        "rssi": getattr(d, 'rssi', None)
                    })
            return printers

        printers = asyncio.run(do_scan())
        return jsonify({"ok": True, "printers": printers})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    print(f"Print Agent starting...")
    print(f"Config: {CONFIG_PATH}")
    print(f"Backends: USB={'yes' if USB_AVAILABLE else 'no'}, BLE={'yes' if BLE_AVAILABLE else 'no'}")
    print(f"Listening on http://127.0.0.1:5001")
    print(f"Endpoints:")
    print(f"  GET  /health - Health check")
    print(f"  POST /print  - Print a label")
    print(f"  GET  /scan   - Scan for BLE printers")
    app.run(host='127.0.0.1', port=5001, debug=False)
