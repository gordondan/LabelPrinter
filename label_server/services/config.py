from __future__ import annotations

import json
from typing import Any, Dict
from .util import BASE_DIR


def load_config() -> Dict[str, Any]:
    """Load optional config/config.json. Returns dict (empty if missing)."""
    cfg_path = BASE_DIR / 'config' / 'config.json'
    if not cfg_path.is_file():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def get_gpio_config() -> Dict[str, Any]:
    cfg = load_config().get('gpio', {}) or {}
    return {
        'enabled': bool(cfg.get('enabled', False)),
        'idle_shutdown_sec': int(cfg.get('idle_shutdown_sec', 30)),
        'pin': int(cfg.get('today_button_pin', cfg.get('pin', 26))),
        'edge': str(cfg.get('today_button_edge', cfg.get('edge', 'FALLING'))),
        'pull': str(cfg.get('today_button_pull', cfg.get('pull', 'UP'))),
        'bounce_ms': int(cfg.get('today_button_bounce_ms', cfg.get('bounce_ms', 200))),
        'action': str(cfg.get('today_button_action', cfg.get('action', 'PRINT_TODAY'))),
    }
