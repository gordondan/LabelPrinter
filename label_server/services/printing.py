from __future__ import annotations

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


def load_printer_config():
    import json as _json
    cfg_path = get_config_file_for_os()
    if not cfg_path.is_file():
        return None, None
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = _json.load(f)
        printers = cfg.get('printers') or {}
        pcfg = printers.get('RW402B') or essential_defaults
        return cfg, pcfg
    except Exception:
        return None, None


def print_png_via_ble(p: Path):
    if RW402BPrinter is None:
        return False, {'error': 'BLE printer module not available on this host'}, 500

    cfg, pcfg = load_printer_config()
    if pcfg is None:
        return False, {'error': 'Printer config not found'}, 500

    try:
        img = Image.open(p)
    except Exception as e:
        return False, {'error': f'Failed to open image: {e}'}, 500

    try:
        dpi = int(pcfg.get('dpi', 203))
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
        # Choose printer name on Windows (use configured default_printer); Linux ignores this parameter
        printer_name = None
        if sys.platform.lower().startswith('win'):
            try:
                printer_name = (cfg or {}).get('default_printer')
            except Exception:
                printer_name = None
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
            call_kwargs['printer_name'] = printer_name
            call_kwargs['printer_config'] = pcfg

        pble.print_pil_image(img, **call_kwargs)
        elapsed_sec = time.perf_counter() - t0
        return True, {'ok': True, 'elapsed_sec': round(elapsed_sec, 3), 'method': 'direct_image_printing'}, 200
    except Exception as e:
        return False, {'error': str(e)}, 500
