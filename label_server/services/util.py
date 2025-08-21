from __future__ import annotations

from pathlib import Path
from datetime import datetime
from flask import Response, send_file
from urllib.parse import quote, unquote
import os
import re

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
WWW_DIR = BASE_DIR / 'www'
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def logs_dir() -> Path:
    return BASE_DIR / 'logs'


def past_images_dir() -> Path:
    return BASE_DIR / 'recent'


def find_latest_preview() -> Path | None:
    """Find the most recent preview from the recent folder only."""
    base = past_images_dir()
    if not base.is_dir():
        return None
    newest = None
    newest_ts = -1
    try:
        for p in base.rglob('label_preview.png'):
            try:
                st = p.stat()
            except Exception:
                continue
            if st.st_mtime > newest_ts:
                newest_ts = st.st_mtime
                newest = p
    except Exception:
        return None
    return newest


def find_latest_metrics():
    p = find_latest_preview()
    if not p:
        return None
    m = p.with_name('metrics.json')
    if m.is_file():
        try:
            import json
            return json.loads(m.read_text(encoding='utf-8'))
        except Exception:
            return None
    return None


def parse_metrics_from_stdout(stdout: str):
    try:
        for line in stdout.splitlines():
            if line.startswith('METRICS:'):
                import json
                payload = line.partition('METRICS:')[2].strip()
                return json.loads(payload)
    except Exception:
        pass
    return None


def list_recent_previews(limit: int = 100):
    base = past_images_dir()
    items: list[dict] = []
    if not base.is_dir():
        return []
    try:
        for p in base.rglob('label_preview.png'):
            try:
                stat = p.stat()
            except Exception:
                continue
            if 'deleted' in p.parts:
                continue
            rel = p.resolve().relative_to(BASE_DIR)
            items.append({
                'path': str(rel).replace('\\', '/'),
                'mtime_ts': int(stat.st_mtime),
                'mtime_iso': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                'size': stat.st_size,
            })
        items.sort(key=lambda x: x['mtime_ts'], reverse=True)
        return items[:limit]
    except Exception:
        return []


def relative_to_base(p: Path) -> str | None:
    try:
        pr = p.resolve().relative_to(BASE_DIR)
        return str(pr).replace('\\', '/')
    except Exception:
        return None


def safe_path_from_query(rel_path: str) -> Path | None:
    try:
        target = (BASE_DIR / rel_path).resolve()
        logs = logs_dir().resolve()
        past = past_images_dir().resolve()
        if not (str(target).startswith(str(logs)) or str(target).startswith(str(past))):
            return None
        if not target.is_file():
            return None
        return target
    except Exception:
        return None


def save_request_data(preview_path: Path, request_data: dict):
    try:
        import json
        request_path = preview_path.with_name('request.json')
        normalized_request = normalize_request_for_template_matching(request_data)
        with open(request_path, 'w', encoding='utf-8') as f:
            json.dump({'original_request': request_data, 'normalized_template': normalized_request, 'timestamp': datetime.now().isoformat()}, f, indent=2)
    except Exception:
        pass


def load_request_data(preview_path: Path):
    try:
        import json
        p = preview_path.with_name('request.json')
        if p.is_file():
            data = json.loads(p.read_text(encoding='utf-8'))
            return data.get('original_request'), data.get('normalized_template')
    except Exception:
        pass
    return None, None


def normalize_request_for_template_matching(request_data: dict) -> dict:
    exclude_keys = {'preview_only', 'list', 'count'}
    normalized = {}
    for k, v in request_data.items():
        if k in exclude_keys:
            continue
        # Keep booleans (including False) as they affect layout/templates
        if isinstance(v, bool):
            normalized[k] = v
            continue
        if v is not None and v != '':
            normalized[k] = v
    return normalized


def find_existing_template_match(new_request_data: dict) -> Path | None:
    try:
        import json
        from datetime import datetime as _dt

        normalized_new = normalize_request_for_template_matching(new_request_data)
        past = past_images_dir()
        if not past.is_dir():
            return None

        best_match: Path | None = None
        best_ts = 0
        for p in past.rglob('request.json'):
            if 'deleted' in p.parts:
                continue
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                existing_template = data.get('normalized_template', {})
                original_request = data.get('original_request', {})
                if existing_template == normalized_new:
                    existing_date = original_request.get('date')
                    new_date = new_request_data.get('date')
                    if existing_date and new_date and existing_date != new_date:
                        continue
                    elif existing_date and not new_date:
                        today = _dt.now().strftime('%Y-%m-%d')
                        if existing_date != today:
                            continue
                    elif not existing_date and new_date:
                        continue
                    preview_path = p.with_name('label_preview.png')
                    if preview_path.is_file():
                        ts = preview_path.stat().st_mtime
                        if ts > best_ts:
                            best_match = preview_path
                            best_ts = ts
            except Exception:
                continue
        return best_match
    except Exception:
        return None
