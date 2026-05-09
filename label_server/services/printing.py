from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from PIL import Image
import sys
import time
from typing import Tuple

try:
    from rw402b_ble.printer import RW402BPrinter
except Exception:  # noqa: E722
    RW402BPrinter = None

from .util import BASE_DIR

# If PRINT_AGENT_URL is set, use the print agent instead of direct BLE
# This allows Docker containers to print via a native Mac/Linux agent
PRINT_AGENT_URL = os.environ.get('PRINT_AGENT_URL', '').strip()


def get_config_file_for_os() -> Path:
    system = sys.platform.lower()
    if system.startswith('win'):
        return BASE_DIR / 'config' / 'printer-config-windows.json'
    elif system.startswith('linux'):
        return BASE_DIR / 'config' / 'printer-config-linux.json'
    else:
        return BASE_DIR / 'config' / 'printer-config.json'


essential_defaults = {
    'label_width_in': 2.25,
    'label_height_in': 1.25,
    'dpi': 203,
    'gap_mm': 3.0,
    'density': 8,
    'speed': 4,
    'direction': 1,
    'invert': True,
    'bluetooth_wait_time': 4.0,
}


def load_printer_config(printer_name: str = None):
    import json as _json
    cfg_path = get_config_file_for_os()
    if not cfg_path.is_file():
        return None, None
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = _json.load(f)
        printers = cfg.get('printers') or {}
        # Use specified printer or default
        if printer_name and printer_name in printers:
            pcfg = printers.get(printer_name)
        else:
            # Use default printer or fallback to RW402B
            default_printer = cfg.get('default_printer', 'RW402B')
            pcfg = printers.get(default_printer) or printers.get('RW402B') or essential_defaults
        return cfg, pcfg
    except Exception:
        return None, None


def print_via_agent(p: Path, printer_name: str = None, copies: int = 1):
    """Send print job to the print agent service."""
    import urllib.request
    import json as _json

    try:
        img = Image.open(p)
        img_w_px, img_h_px = img.size
        # Convert to PNG bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        image_base64 = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        return False, {'error': f'Failed to load image: {e}'}, 500

    payload = {
        'image_base64': image_base64,
        'copies': copies,
        'image_width_px': img_w_px,
        'image_height_px': img_h_px,
    }
    if printer_name:
        payload['printer_name'] = printer_name

    try:
        t0 = time.perf_counter()
        req = urllib.request.Request(
            f"{PRINT_AGENT_URL}/print",
            data=_json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read().decode('utf-8'))

        elapsed_sec = time.perf_counter() - t0

        if result.get('ok'):
            return True, {'ok': True, 'elapsed_sec': round(elapsed_sec, 3), 'method': 'print_agent'}, 200
        else:
            return False, {'error': result.get('error', 'Unknown error from print agent')}, 500

    except urllib.error.URLError as e:
        return False, {'error': f'Failed to connect to print agent: {e}'}, 500
    except Exception as e:
        return False, {'error': f'Print agent error: {e}'}, 500


def print_png_via_ble(p: Path, printer_name: str = None):
    # If print agent URL is configured, use it instead of direct BLE
    if PRINT_AGENT_URL:
        return print_via_agent(p, printer_name)

    if RW402BPrinter is None:
        return False, {'error': 'BLE printer module not available on this host'}, 500

    cfg, pcfg = load_printer_config(printer_name)
    if pcfg is None:
        return False, {'error': 'Printer config not found'}, 500

    try:
        img = Image.open(p)
    except Exception as e:
        return False, {'error': f'Failed to open image: {e}'}, 500

    try:
        dpi = int(pcfg.get('dpi', 203))
        # Derive label dimensions from the image so the user-selected label size
        # propagates to the printer's TSPL SIZE command. The image was rendered at
        # exactly label_width_in*dpi by label_height_in*dpi pixels (see
        # label-printer.py:779-780), so this inversion recovers the chosen size.
        # Fall back to printer config dimensions if the image isn't usable.
        try:
            img_w_in = img.width / dpi
            img_h_in = img.height / dpi
            if img_w_in > 0 and img_h_in > 0:
                w_in, h_in = img_w_in, img_h_in
            else:
                w_in = float(pcfg.get('label_width_in', 2.25))
                h_in = float(pcfg.get('label_height_in', 1.25))
        except Exception:
            w_in = float(pcfg.get('label_width_in', 2.25))
            h_in = float(pcfg.get('label_height_in', 1.25))
        gap_mm = float(pcfg.get('gap_mm', 3.0))
        density = int(pcfg.get('density', 8))
        speed = int(pcfg.get('speed', 4))
        direction = int(pcfg.get('direction', 1))
        invert = bool(pcfg.get('invert', True))
        ble_mac = pcfg.get('ble_mac') or None
        # Optional BLE tunables
        prefer_resp = bool(pcfg.get('prefer_write_with_response', True))
        throttle_ms = int(pcfg.get('write_throttle_ms', 0))
        chunk_size = int(pcfg.get('write_chunk_size', 20))
    except Exception as e:
        return False, {'error': f'Invalid printer config: {e}'}, 500

    try:
        t0 = time.perf_counter()
        # On Windows, RW402BPrinter may accept a config dict; on Linux we pass BLE tunables
        extra_kwargs = {}
        if sys.platform.lower().startswith('win'):
            extra_kwargs['config'] = cfg or {}
            pble = RW402BPrinter(addr=ble_mac, timeout=float(pcfg.get('bluetooth_wait_time', 4.0)),
                                 dpi=dpi, invert=invert, **extra_kwargs)
        else:
            pble = RW402BPrinter(addr=ble_mac, timeout=float(pcfg.get('bluetooth_wait_time', 4.0)),
                                 dpi=dpi, invert=invert,
                                 prefer_resp=prefer_resp, throttle_ms=throttle_ms, chunk_size=chunk_size,
                                 **extra_kwargs)
        # Choose printer name on Windows (use windows_printer_name from printer config); Linux ignores this parameter
        printer_name_win = None
        if sys.platform.lower().startswith('win'):
            try:
                # Use windows_printer_name from the selected printer config
                printer_name_win = pcfg.get('windows_printer_name')
                if not printer_name_win:
                    # Fallback to default_printer from global config
                    printer_name_win = (cfg or {}).get('default_printer')
            except Exception:
                printer_name_win = None
        # Build args common to both platforms
        call_kwargs = dict(
            label_w_mm=w_in * 25.4,
            label_h_mm=h_in * 25.4,
            gap_mm=gap_mm,
            density=density,
            speed=speed,
            direction=direction,
            x=0, y=0, mode=0,
        )
        # Only Windows backend supports these parameters
        if sys.platform.lower().startswith('win'):
            call_kwargs['printer_name'] = printer_name_win
            call_kwargs['printer_config'] = pcfg

        pble.print_pil_image(img, **call_kwargs)
        elapsed_sec = time.perf_counter() - t0
        return True, {'ok': True, 'elapsed_sec': round(elapsed_sec, 3), 'method': 'direct_image_printing'}, 200
    except Exception as e:
        return False, {'error': str(e)}, 500
