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
    except Exception as e:
        return False, {'error': f'Invalid printer config: {e}'}, 500

    try:
        t0 = time.perf_counter()
        pble = RW402BPrinter(addr=ble_mac, timeout=float(pcfg.get('bluetooth_wait_time', 4.0)),
                              dpi=dpi, invert=invert)
        pble.print_pil_image(
            img,
            label_w_mm=w_in * 25.4,
            label_h_mm=h_in * 25.4,
            gap_mm=gap_mm,
            density=density,
            speed=speed,
            direction=direction,
            x=0, y=0, mode=0
        )
        elapsed_sec = time.perf_counter() - t0
        return True, {'ok': True, 'elapsed_sec': round(elapsed_sec, 3), 'method': 'direct_image_printing'}, 200
    except Exception as e:
        return False, {'error': str(e)}, 500
