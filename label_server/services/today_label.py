from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from .util import BASE_DIR, past_images_dir, find_latest_preview, relative_to_base, save_request_data


TODAY_DIR = past_images_dir() / 'today'
TODAY_PNG = TODAY_DIR / 'today_label.png'


def _is_png_for_today(p: Path) -> bool:
    try:
        ts = p.stat().st_mtime
        d = datetime.fromtimestamp(ts).date()
        return d == datetime.now().date()
    except Exception:
        return False


def _build_today_cmd() -> list[str]:
    script_path = (BASE_DIR / 'label-printer.py').resolve()
    exe = sys.executable or 'python3'
    # -p preview, -o include today's date, -c 1 count
    return [exe, str(script_path), '-p', '-o', '-c', '1']


def ensure_today_label(logger=None, force: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Ensure recent/today/today_label.png exists and is from today.
    Returns (ready, rel_path) where rel_path is relative to BASE_DIR or None.
    """
    try:
        TODAY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    if TODAY_PNG.is_file() and not force and _is_png_for_today(TODAY_PNG):
        return True, relative_to_base(TODAY_PNG)

    # Generate a fresh preview for today's label
    try:
        cmd = _build_today_cmd()
        env = os.environ.copy()
        env.setdefault('LABEL_BORDER_ENABLED', '1')
        if logger:
            try:
                logger.info("Generating today label: %s", ' '.join(cmd))
            except Exception:
                pass
        import subprocess, time as _time
        t0 = _time.perf_counter()
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if logger:
            try:
                logger.info("Today label preview rc=%s in %.3fs", res.returncode, _time.perf_counter()-t0)
                if res.returncode != 0:
                    logger.error("stderr: %s", (res.stderr or res.stdout or '').strip())
            except Exception:
                pass
        if res.returncode != 0:
            return False, None
        prev = find_latest_preview()
        if not prev or not prev.is_file():
            return False, None
        # Copy preview to TODAY_PNG
        try:
            shutil.copy2(str(prev), str(TODAY_PNG))
        except Exception:
            return False, None
        # Save request.json alongside for matching/debug
        try:
            req = { 'show_date': True, 'border': True, 'count': 1, 'preview_only': True }
            save_request_data(TODAY_PNG, req)
        except Exception:
            pass
        return True, relative_to_base(TODAY_PNG)
    except Exception:
        return False, None


def get_today_status() -> dict:
    ready = TODAY_PNG.is_file() and _is_png_for_today(TODAY_PNG)
    rel = relative_to_base(TODAY_PNG) if TODAY_PNG.is_file() else None
    return { 'ready': bool(ready), 'rel_path': rel }
