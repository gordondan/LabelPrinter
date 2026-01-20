from __future__ import annotations

from flask import Blueprint, jsonify, request, Response, send_file, current_app
from werkzeug.utils import secure_filename
import os
import sys
import time
import html
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote
from datetime import datetime
import traceback

from ..services.util import (
    allowed_file,
    find_latest_preview,
    find_latest_metrics,
    list_recent_previews,
    relative_to_base,
    safe_path_from_query,
    save_request_data,
    find_existing_template_match,
)
from ..services.printing import print_png_via_ble
from ..services.jobs import JobStatus
from ..services.today_label import ensure_today_label, get_today_status
from ..services.events import bus
from flask import stream_with_context

api_bp = Blueprint('api', __name__)


@api_bp.get('/health')
def health_check():
    """Health check endpoint for Docker and watchdog."""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200
@api_bp.get('/api/events')
def sse_events():
    q = bus.subscribe()
    def gen():
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            pass
        finally:
            bus.unsubscribe(q)
    resp = Response(stream_with_context(gen()), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


@api_bp.get('/api/pi-label/options')
def get_pi_label_options():
    options = [
        {"flag": "-c", "long_flag": "--count", "type": "int", "default": 1, "description": "Number of labels to print"},
        {"flag": "-m", "long_flag": "--message", "type": "string", "description": "Custom message to print in center of label"},
        {"flag": "-b", "long_flag": "--border-message", "type": "string", "description": "Custom border message for top and bottom borders"},
        {"flag": "-s", "long_flag": "--side-border", "type": "string", "description": "Custom side border message (left/right, rotated)"},
        {"flag": "-i", "long_flag": "--image", "type": "string", "description": "Path to PNG image to include (cropped to fit)"},
        {"flag": "-o", "long_flag": "--show-date", "type": "bool", "default": False, "description": "Show dates on the label (hidden by default)"},
    {"flag": None, "long_flag": "--border", "type": "bool", "default": True, "description": "Include a decorative border around the label"},
    ]
    return jsonify({"script": "label-printer.py", "endpoint": "/app/pi-label/options", "options": options})


@api_bp.get('/api/recent')
def api_recent():
    try:
        limit = int(request.args.get('limit', '100'))
    except Exception:
        limit = 100
    items = list_recent_previews(limit)
    for it in items:
        q = quote(it['path'])
        it['image_url'] = f"/preview/file?path={q}&ts={it['mtime_ts']}"
    return jsonify({'items': items})


@api_bp.get('/preview/file')
def preview_by_path():
    rel = request.args.get('path')
    if not rel:
        return Response('Missing path', mimetype='text/plain'), 400
    p = safe_path_from_query(unquote(rel))
    if not p:
        return Response('Invalid path', mimetype='text/plain'), 400
    resp = send_file(str(p), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@api_bp.post('/api/delete')
def api_delete():
    data = request.get_json(silent=True) or {}
    rel = data.get('path')
    if not rel:
        return jsonify({'error': 'Missing path'}), 400
    p = safe_path_from_query(rel)
    if not p:
        return jsonify({'error': 'Invalid path'}), 400

    base = Path(os.path.dirname(__file__)).resolve().parent.parent
    try:
        past_root = base / 'recent'
        logs_root = base / 'logs'
        rp = p.resolve()
        if str(rp).startswith(str(past_root.resolve())):
            rel_to_root = rp.relative_to(past_root.resolve())
        elif str(rp).startswith(str(logs_root.resolve())):
            rel_to_root = rp.relative_to(logs_root.resolve())
        else:
            return jsonify({'error': 'Path not under expected roots'}), 400

        deleted_root = past_root / 'deleted'
        dest_dir = deleted_root / rel_to_root.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / p.name
        p.rename(dest_path)

        for side_name in ('request.json', 'metrics.json'):
            sf = rp.with_name(side_name)
            if sf.is_file():
                try:
                    sf.rename(dest_path.with_name(side_name))
                except Exception:
                    pass

        return jsonify({'ok': True, 'deleted_to': str(dest_path.relative_to(base)).replace('\\','/')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.get('/preview.png')
def latest_preview_png():
    p = find_latest_preview()
    if not p:
        return Response('Preview not found', mimetype='text/plain'), 404
    resp = send_file(str(p), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@api_bp.post('/api/upload')
def upload_image_file():
    if 'imageFile' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['imageFile']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'message': f'File "{filename}" uploaded successfully!', 'filePath': filepath}), 200
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PNG, JPG, or GIF.'}), 400


@api_bp.post('/api/batch/parse')
def api_batch_parse():
    """Parse a CSV file into rows using Python's csv module for portability."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    f = request.files['file']
    if not f or not f.filename:
        return jsonify({'error': 'No file selected'}), 400
    try:
        import csv, io
        data = f.read()
        text = data.decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            norm = {}
            for k, v in row.items():
                if k is None:
                    continue
                key = str(k).strip().lower().replace(' ', '_')
                val = (v or '').strip()
                norm[key] = val
            # Map to expected fields
            def _bool(s):
                return str(s).strip().lower() in ('1','true','yes','y','on')
            out = {
                'message': norm.get('message', ''),
                'border_message': norm.get('border_message', norm.get('border', '')),
                'side_border': norm.get('side_border', ''),
                'show_date': _bool(norm.get('show_date', norm.get("today", ''))),
                'border': _bool(norm.get('border_enabled', norm.get('border', 'true'))),
                'image': norm.get('image', norm.get('image_path','')),
                'count': int(norm.get('count', '1') or '1'),
            }
            rows.append(out)
        return jsonify({'rows': rows, 'fields': reader.fieldnames}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.post('/api/reprint')
def api_reprint():
    data = request.get_json(silent=True) or {}
    rel = data.get('path')
    printer_name = data.get('printer')
    if not rel:
        return jsonify({'error': 'Missing path'}), 400
    p = safe_path_from_query(rel)
    if not p:
        return jsonify({'error': 'Invalid path'}), 400

    # Try to load original request and regenerate
    from ..services.util import load_request_data
    original_request, _ = load_request_data(p)
    if original_request:
        try:
            updated_request = dict(original_request)
            # 'date' is no longer a CLI flag; keep it only as part of user content if present
            updated_request.pop('date', None)
            updated_request['preview_only'] = False
            ok, errors = validate_payload(updated_request)
            if not ok:
                return jsonify({'error': f'Invalid original request data: {errors}'}), 400
            cmd = build_command_from_payload(updated_request)
            t0 = time.perf_counter()
            env = os.environ.copy()
            env['LABEL_BORDER_ENABLED'] = '1' if updated_request.get('border', True) else '0'
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            elapsed_sec = time.perf_counter() - t0
            if result.returncode == 0:
                # Mark as printed
                save_request_data(p, original_request, printed=True)
                return jsonify({'ok': True, 'elapsed_sec': round(elapsed_sec, 3), 'method': 'template_regeneration', 'stdout': (result.stdout or '').strip()})
            else:
                return jsonify({'error': f'Template regeneration failed: {result.stderr}', 'fallback_reason': 'Falling back to direct image printing'}), 400
        except Exception:
            pass

    # Fallback: direct BLE image printing - also mark as printed
    if original_request:
        save_request_data(p, original_request, printed=True)
    ok, resp, code = print_png_via_ble(p, printer_name)
    return jsonify(resp), code


# ----- Label preview/print helpers -----

def build_command_from_payload(payload: dict):
    # Use the repo's script name
    script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'label-printer.py')
    script_path = os.path.normpath(script_path)
    cmd = [sys.executable or 'python3', script_path]
    if payload.get('list') is True:
        cmd.append('-l')
    if payload.get('show_date') is True:
        cmd.append('-o')
    if payload.get('preview_only') is True:
        cmd.append('-p')

    count = payload.get('count')
    if count is not None:
        try:
            count_val = int(count)
            if count_val > 0:
                cmd.extend(['-c', str(count_val)])
        except (TypeError, ValueError):
            pass

    mapping = [
        ('message', '-m'), ('border_message', '-b'), ('side_border', '-s'), ('image', '-i'),
    ]
    for key, flag in mapping:
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            cmd.extend([flag, val.strip()])

    # Handle label size
    label_size = payload.get('label_size')
    if isinstance(label_size, str) and label_size.strip():
        cmd.extend(['-z', label_size.strip()])

    return cmd


def validate_payload(payload: dict):
    errors = []
    if 'count' in payload and payload['count'] is not None:
        try:
            count_val = int(payload['count'])
            if count_val <= 0:
                errors.append("'count' must be a positive integer")
        except (TypeError, ValueError):
            errors.append("'count' must be an integer")

    # 'date' is no longer a script parameter; when present in payload it's user text content.

    img = payload.get('image')
    if img:
        base_path = Path(os.path.dirname(__file__)).resolve().parents[1]
        if not isinstance(img, str) or not (base_path / img).is_file():
            errors.append(f"'image' path does not exist on server: {html.escape(str(img))}")

    return (len(errors) == 0, errors)


@api_bp.post('/api/pi-label/preview')
def api_pi_label_preview():
    data = request.get_json(silent=True) or {}
    data = dict(data)
    data['preview_only'] = True
    try:
        current_app.logger.info("/api/pi-label/preview payload: %s", data)
    except Exception:
        pass

    ok, errors = validate_payload(data)
    if not ok:
        current_app.logger.warning("Preview validation failed: %s", errors)
        return jsonify({'errors': errors}), 400

    cmd = build_command_from_payload(data)
    script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'label-printer.py')
    script_path = os.path.normpath(script_path)
    current_app.logger.info("Preview executing: %s", ' '.join(map(str, cmd)))
    current_app.logger.info("CWD: %s | script exists: %s", os.getcwd(), os.path.isfile(script_path))

    try:
        # Try template reuse: if a recent request.json matches, reuse the preview directly
        reused_preview = find_existing_template_match(data)
        if reused_preview:
            current_app.logger.info("Reusing existing preview: %s", reused_preview)
            # Mirror request data next to reused preview
            try:
                save_request_data(reused_preview, data)
            except Exception:
                pass
            metrics = find_latest_metrics()
            ts = int(reused_preview.stat().st_mtime)
            preview_url = f"/preview/file?path={quote(relative_to_base(reused_preview))}&ts={ts}"
            return jsonify({
                'ok': True,
                'command': cmd,
                'returncode': 0,
                'stdout': 'Reused existing preview',
                'stderr': '',
                'elapsed_sec': 0,
                'preview_url': preview_url,
                'preview_path': relative_to_base(reused_preview),
                'metrics': metrics,
                'reused': True,
            }), 200

        t0 = time.perf_counter()
        env = os.environ.copy()
        env['LABEL_BORDER_ENABLED'] = '1' if data.get('border', True) else '0'
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        elapsed_sec = time.perf_counter() - t0
        current_app.logger.info("Preview subprocess rc=%s in %.3fs", result.returncode, elapsed_sec)

        preview_path = find_latest_preview()
        preview_url = None
        rel_path = None
        if preview_path:
            ts = int(preview_path.stat().st_mtime)
            preview_url = f"/preview.png?ts={ts}"
            rel_path = relative_to_base(preview_path)
            # Save request.json alongside the preview for future template reuse
            try:
                save_request_data(preview_path, data)
            except Exception:
                pass

        metrics = find_latest_metrics()
        if result.returncode != 0:
            # Log details for debugging
            try:
                current_app.logger.error("Preview failed. stdout: %s\nstderr: %s", (result.stdout or '').strip(), (result.stderr or '').strip())
            except Exception:
                pass
        error_msg = None
        if result.returncode != 0:
            error_msg = (result.stderr or result.stdout or 'Preview failed').strip()
        return jsonify({
            'ok': result.returncode == 0,
            'command': cmd,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'elapsed_sec': round(elapsed_sec, 3),
            'preview_url': preview_url,
            'preview_path': rel_path,
            'metrics': metrics,
            **({'error': error_msg} if error_msg else {}),
        }), (200 if result.returncode == 0 else 500)
    except FileNotFoundError:
        current_app.logger.exception("label-printer.py not found for preview")
        return jsonify({'error': 'label-printer.py not found', 'command': cmd}), 500
    except Exception as e:
        current_app.logger.error("Unhandled exception in api_pi_label_preview: %s\n%s", str(e), traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@api_bp.post('/api/pi-label/print')
def post_pi_label_print():
    data = request.get_json(silent=True) or {}
    try:
        current_app.logger.info("/api/pi-label/print payload: %s", data)
    except Exception:
        pass

    rel = data.get('path')
    printer_name = data.get('printer')
    if isinstance(rel, str) and rel.strip():
        p = safe_path_from_query(unquote(rel.strip()))
        if not p:
            return jsonify({'error': 'Invalid path'}), 400
        current_app.logger.info("Queueing print PNG at: %s", p)

        # Mark as printed in request.json
        from ..services.util import load_request_data
        original_request, _ = load_request_data(p)
        if original_request:
            save_request_data(p, original_request, printed=True)

        jq = getattr(current_app, 'job_queue', None)
        if not jq:
            ok, resp, code = print_png_via_ble(p, printer_name)
            return jsonify(resp), code
        # Enqueue direct image print
        job = jq.enqueue('print', lambda: print_png_via_ble(p, printer_name), payload={'path': rel, 'printer': printer_name})
        return jsonify({'queued': True, 'job_id': job.id, 'status': job.status}), 202

    ok, errors = validate_payload(data)
    if not ok:
        current_app.logger.warning("Print validation failed: %s", errors)
        return jsonify({'errors': errors}), 400

    cmd = build_command_from_payload(data)
    script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'label-printer.py')
    script_path = os.path.normpath(script_path)
    current_app.logger.info("Legacy print executing: %s", ' '.join(map(str, cmd)))
    current_app.logger.info("CWD: %s | script exists: %s", os.getcwd(), os.path.isfile(script_path))

    # Queue legacy generation+print as a job to return immediately
    jq = getattr(current_app, 'job_queue', None)
    if not jq:
        # Fallback to original blocking behavior
        try:
            # Try template reuse first to avoid regeneration when identical
            reused_preview = find_existing_template_match(data)
            if reused_preview:
                current_app.logger.info("Reusing existing preview for print: %s", reused_preview)
                try:
                    save_request_data(reused_preview, data)
                except Exception:
                    pass
                ok, resp, code = print_png_via_ble(reused_preview, printer_name)
                return jsonify({'reused': True, **resp}), code
        except Exception:
            pass
        return jsonify({'error': 'Job queue unavailable'}), 503
    # Build job closure
    def _job_fn():
        try:
            reused_preview = find_existing_template_match(data)
            if reused_preview:
                try:
                    save_request_data(reused_preview, data, printed=True)
                except Exception:
                    pass
                return print_png_via_ble(reused_preview, printer_name)
            env = os.environ.copy()
            env['LABEL_BORDER_ENABLED'] = '1' if data.get('border', True) else '0'
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout or 'Print generation failed').strip())
            preview_path = find_latest_preview()
            if not preview_path:
                raise RuntimeError('No preview generated')
            try:
                save_request_data(preview_path, data, printed=True)
            except Exception:
                pass
            return print_png_via_ble(preview_path, printer_name)
        except Exception as e:
            return False, {'error': str(e)}, 500
    job = jq.enqueue('print', _job_fn, payload={'payload': data, 'printer': printer_name})
    return jsonify({'queued': True, 'job_id': job.id, 'status': job.status}), 202


@api_bp.get('/api/jobs')
def api_jobs_list():
    jq = getattr(current_app, 'job_queue', None)
    if not jq:
        return jsonify({'jobs': []})
    jobs = jq.list()
    return jsonify({'jobs': [
        {
            'id': j.id,
            'type': j.type,
            'status': j.status,
            'created_at': j.created_at,
            'started_at': j.started_at,
            'finished_at': j.finished_at,
            'error': j.error,
        } for j in jobs
    ]})


@api_bp.get('/api/jobs/<job_id>')
def api_jobs_get(job_id: str):
    jq = getattr(current_app, 'job_queue', None)
    if not jq:
        return jsonify({'error': 'Job queue unavailable'}), 503
    j = jq.get(job_id)
    if not j:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id': j.id,
        'type': j.type,
        'status': j.status,
        'created_at': j.created_at,
        'started_at': j.started_at,
        'finished_at': j.finished_at,
        'error': j.error,
        'result': j.result if isinstance(j.result, dict) else None,
    })


@api_bp.get('/api/jobs/counts')
def api_jobs_counts():
    jq = getattr(current_app, 'job_queue', None)
    if not jq:
        return jsonify({'queued': 0, 'running': 0, 'total_active': 0})
    return jsonify(jq.counts())


@api_bp.get('/api/today/status')
def api_today_status():
    return jsonify(get_today_status())


@api_bp.post('/api/today/ensure')
def api_today_ensure():
    force = bool((request.get_json(silent=True) or {}).get('force'))
    # Run in background via job queue to avoid blocking UI
    jq = getattr(current_app, 'job_queue', None)
    if jq:
        def _job():
            ok, rel = ensure_today_label(logger=current_app.logger, force=force)
            return {'ok': ok, 'rel_path': rel}
        job = jq.enqueue('ensure-today', _job, payload={'force': force})
        return jsonify({'queued': True, 'job_id': job.id}), 202
    ok, rel = ensure_today_label(logger=current_app.logger, force=force)
    return jsonify({'ok': ok, 'rel_path': rel})
