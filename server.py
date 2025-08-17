from flask import Flask, jsonify, request, Response, send_from_directory, send_file
from werkzeug.utils import secure_filename # <-- ADDED: For sanitizing filenames
import subprocess
import sys
import os
import html
import re
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, unquote
from PIL import Image

# Try to import BLE printer for direct reprint support
try:
    from rw402b_ble.printer import RW402BPrinter
except Exception:  # noqa: E722
    RW402BPrinter = None


app = Flask(__name__)

# --- Configuration for File Uploads ---
# <-- ADDED SECTION START -->
UPLOAD_FOLDER = 'uploads' # Folder for user-uploaded images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a-super-secret-key-for-sessions' # Good practice for Flask apps
# <-- ADDED SECTION END -->


@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET'])
def root_index():
    """Serve the main UI at the root path for convenience."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), "www"), "index.html")

@app.route('/<path:filename>')
def serve_static_files(filename):
    """Serves any static file from the 'www' directory."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'www'), filename)

@app.route("/api/pi-label/options", methods=["GET"])
def get_pi_label_options():
    """
    Return the available CLI options for pi-label-printer.py as JSON.
    This mirrors the argparse flags defined in pi-label-printer.py.
    """
    options = [
        {
            "flag": "-c",
            "long_flag": "--count",
            "type": "int",
            "default": 1,
            "description": "Number of labels to print",
        },
        {
            "flag": "-d",
            "long_flag": "--date",
            "type": "string",
            "format": "YYYY-MM-DD",
            "description": "Specific date to print (default: today)",
        },
        {
            "flag": "-m",
            "long_flag": "--message",
            "type": "string",
            "description": "Custom message to print in center of label",
        },
        {
            "flag": "-b",
            "long_flag": "--border-message",
            "type": "string",
            "description": "Custom border message for top and bottom borders",
        },
        {
            "flag": "-s",
            "long_flag": "--side-border",
            "type": "string",
            "description": "Custom side border message (left/right, rotated)",
        },
        {
            "flag": "-i",
            "long_flag": "--image",
            "type": "string",
            "description": "Path to PNG image to include (cropped to fit)",
        },
        {
            "flag": "-o",
            "long_flag": "--show-date",
            "type": "bool",
            "default": False,
            "description": "Show dates on the label (hidden by default)",
        },
        {
            "flag": "-p",
            "long_flag": "--preview-only",
            "type": "bool",
            "default": False,
            "description": "Generate label image only (do not print)",
        },
    ]

    return jsonify({
        "script": "pi-label-printer.py",
        "endpoint": "/app/pi-label/options",
        "options": options,
    })


@app.route("/app/pi-label", methods=["GET"])
def pi_label_form():
    """Serve the HTML UI (now also available at /app via index.html)."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), "www"), "index.html")


# --- Helpers ---

# <-- ADDED HELPER FUNCTION -->
def allowed_file(filename):
    """Checks if the file extension is allowed for uploads."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _find_latest_preview():
    """Search for the newest label_preview.png under logs/ and project root."""
    base_dir = Path(os.path.dirname(__file__))
    candidates = []
    root_preview = base_dir / "label_preview.png"
    if root_preview.is_file():
        candidates.append(root_preview)

    logs_dir = base_dir / "logs"
    if logs_dir.is_dir():
        try:
            for p in logs_dir.rglob("label_preview.png"):
                if p.is_file():
                    candidates.append(p)
        except Exception:
            pass

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _find_latest_metrics():
    """If a metrics.json exists next to the latest preview, load and return it."""
    p = _find_latest_preview()
    if not p:
        return None
    metrics_path = p.with_name('metrics.json')
    if metrics_path.is_file():
        try:
            import json
            with open(metrics_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_request_data(preview_path: Path, request_data: dict):
    """Save the original request data next to the generated preview for template reprinting."""
    try:
        import json
        request_path = preview_path.with_name('request.json')
        # Create a normalized request for deduplication
        normalized_request = _normalize_request_for_template_matching(request_data)
        
        with open(request_path, 'w', encoding='utf-8') as f:
            json.dump({
                'original_request': request_data,
                'normalized_template': normalized_request,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
    except Exception:
        pass  # Don't fail the main operation if we can't save request data


def _mirror_request_data_to_past_images(logs_preview_path: Path):
    """Mirror request.json from logs to recent after label generation."""
    try:
        # Check if we have a logger-generated request file to mirror
        import sys
        sys.path.append(str(Path(__file__).parent))
        from logger import create_logger
        
        # Create a temporary logger to use its mirror functionality
        logs_root = _logs_dir()
        if str(logs_preview_path).startswith(str(logs_root)):
            log_dir = logs_preview_path.parent
            # Create logger with the specific session directory
            temp_logger = create_logger(str(logs_root))
            temp_logger.current_log_dir = log_dir
            temp_logger.mirror_request_file()
    except Exception as e:
        pass


def _load_request_data(preview_path: Path):
    """Load the original request data for a preview if available."""
    try:
        import json
        request_path = preview_path.with_name('request.json')
        if request_path.is_file():
            with open(request_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('original_request'), data.get('normalized_template')
    except Exception:
        pass
    return None, None


def _normalize_request_for_template_matching(request_data: dict) -> dict:
    """Create a normalized request for template matching."""
    # Remove fields that don't affect the template
    exclude_keys = {'preview_only', 'list', 'count'}
    normalized = {}
    
    for k, v in request_data.items():
        if k in exclude_keys:
            continue
        # Only include non-empty values
        if v is not None and v != '' and v != False:
            normalized[k] = v
    
    return normalized


def _find_existing_template_match(new_request_data: dict) -> Path | None:
    """Find existing label with the same template (request pattern), if any."""
    try:
        import json
        from datetime import datetime
        
        # Normalize the new request
        normalized_new = _normalize_request_for_template_matching(new_request_data)
        
        # Only search recent directory (logs is write-once only)
        past_images = _past_images_dir()
        if not past_images.is_dir():
            return None
        
        found_files = []
        best_match = None
        best_timestamp = 0
        
        for p in past_images.rglob("request.json"):
            if "deleted" in p.parts:
                continue
            found_files.append(str(p))
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    existing_template = data.get('normalized_template', {})
                    original_request = data.get('original_request', {})
                    
                    if existing_template == normalized_new:
                        # Check if this template has a fixed date that doesn't match today
                        existing_date = original_request.get('date')
                        new_date = new_request_data.get('date')
                        
                        # If either has a specific date and they don't match, skip this template
                        if existing_date and new_date and existing_date != new_date:
                            continue
                        elif existing_date and not new_date:
                            # Existing has fixed date, new wants current date - check if it matches today
                            today = datetime.now().strftime('%Y-%m-%d')
                            if existing_date != today:
                                continue
                        elif not existing_date and new_date:
                            # Existing uses current date, new wants fixed date - don't reuse
                            continue
                        
                        # Found a compatible match, check if preview exists
                        preview_path = p.with_name('label_preview.png')
                        if preview_path.is_file():
                            # Get the timestamp and keep the most recent match
                            timestamp = preview_path.stat().st_mtime
                            if timestamp > best_timestamp:
                                best_match = preview_path
                                best_timestamp = timestamp
            except Exception as e:
                continue
        
        if best_match:
            print(f"Template reused: {best_match.parent.name}")
            return best_match
    except Exception as e:
        pass
    return None


def _parse_metrics_from_stdout(stdout: str):
    """Look for a line like 'METRICS: {json}' and parse it."""
    try:
        for line in stdout.splitlines():
            if line.startswith('METRICS:'):
                import json
                payload = line.partition('METRICS:')[2].strip()
                return json.loads(payload)
    except Exception:
        pass
    return None


def _logs_dir() -> Path:
    return Path(os.path.dirname(__file__)) / "logs"


def _past_images_dir() -> Path:
    return Path(os.path.dirname(__file__)) / "recent"


def _list_recent_previews(limit: int = 100):
    # Prefer recent as the canonical recent source; fallback to logs
    base = _past_images_dir()
    if not base.is_dir():
        base = _logs_dir()
    items = []
    if not base.is_dir():
        return []
    try:
        for p in base.rglob("label_preview.png"):
            try:
                stat = p.stat()
            except Exception:
                continue
            # Skip files in deleted subdirectory
            if "deleted" in p.parts:
                continue
            rel = p.relative_to(Path(os.path.dirname(__file__)))
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


def _safe_path_from_query(rel_path: str) -> Path | None:
    """Ensure requested path is inside the workspace and under recent/.* or logs/.*"""
    try:
        base = Path(os.path.dirname(__file__))
        target = (base / rel_path).resolve()
        logs = (_logs_dir()).resolve()
        past = (_past_images_dir()).resolve()
        if not (str(target).startswith(str(logs)) or str(target).startswith(str(past))):
            return None
        if not target.is_file():
            return None
        return target
    except Exception:
        return None


def _get_config_file_for_os() -> Path:
    system = sys.platform.lower()
    base = Path(os.path.dirname(__file__))
    if system.startswith('win'):
        return base / 'config' / 'printer-config-windows.json'
    elif system.startswith('linux'):
        return base / 'config' / 'printer-config-linux.json'
    else:
        return base / 'config' / 'printer-config.json'


def _load_printer_config():
    import json as _json
    cfg_path = _get_config_file_for_os()
    if not cfg_path.is_file():
        return None, None
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = _json.load(f)
        printer_name = 'RW402B'
        printers = cfg.get('printers') or {}
        pcfg = printers.get(printer_name) or {
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
        return cfg, pcfg
    except Exception:
        return None, None


@app.route('/api/recent', methods=['GET'])
def api_recent():
    """Return recent previews with metadata."""
    try:
        limit = int(request.args.get('limit', '100'))
    except Exception:
        limit = 100
    items = _list_recent_previews(limit)
    # attach image URLs
    for it in items:
        q = quote(it['path'])
        it['image_url'] = f"/preview/file?path={q}&ts={it['mtime_ts']}"
    return jsonify({'items': items})


@app.route('/preview/file', methods=['GET'])
def preview_by_path():
    """Serve a specific preview by relative path (under logs directory)."""
    rel = request.args.get('path')
    if not rel:
        return Response('Missing path', mimetype='text/plain'), 400
    rel = unquote(rel)
    p = _safe_path_from_query(rel)
    if not p:
        return Response('Invalid path', mimetype='text/plain'), 400
    resp = send_file(str(p), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/api/reprint', methods=['POST'])
def api_reprint():
    """Reprint a saved label by regenerating it from the original request data with current dynamic values."""
    data = request.get_json(silent=True) or {}
    rel = data.get('path')
    if not rel:
        return jsonify({'error': 'Missing path'}), 400
    p = _safe_path_from_query(rel)
    if not p:
        return jsonify({'error': 'Invalid path'}), 400

    # Try to load the original request data for template reprinting
    original_request, _ = _load_request_data(p)
    if original_request:
        # Regenerate the label using the original template with current dynamic values
        try:
            # Update dynamic fields like date to current values
            updated_request = original_request.copy()
            # If the original request had date template markers but not a specific date, use today
            if 'message' in updated_request and updated_request['message'] and '{{date}}' in str(updated_request['message']):
                # Template has date placeholder - will be filled by the label generator
                pass  # Keep the template as-is
            elif 'date' not in updated_request or not updated_request['date']:
                # No specific date was provided, don't set one to use today
                updated_request.pop('date', None)
            
            # Set preview_only to False to ensure actual printing
            updated_request['preview_only'] = False
            
            # Validate the updated request
            ok, errors = validate_payload(updated_request)
            if not ok:
                return jsonify({'error': f'Invalid original request data: {errors}'}), 400
            
            cmd = build_command_from_payload(updated_request)
            
            t0 = time.perf_counter()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            elapsed_sec = time.perf_counter() - t0
            
            if result.returncode == 0:
                return jsonify({
                    'ok': True, 
                    'elapsed_sec': round(elapsed_sec, 3),
                    'method': 'template_regeneration',
                    'stdout': result.stdout.strip() if result.stdout else ''
                })
            else:
                # Fall back to direct image printing if regeneration failed
                return jsonify({
                    'error': f'Template regeneration failed: {result.stderr}',
                    'fallback_reason': 'Falling back to direct image printing'
                }), 400
                
        except Exception as e:
            # Fall back to direct image printing if template processing failed
            pass
    
    # Fallback: Direct image printing (original behavior)
    if RW402BPrinter is None:
        return jsonify({'error': 'BLE printer module not available on this host and no template data found'}), 500

    cfg, pcfg = _load_printer_config()
    if pcfg is None:
        return jsonify({'error': 'Printer config not found'}), 500

    try:
        img = Image.open(p)
    except Exception as e:
        return jsonify({'error': f'Failed to open image: {e}'}), 500

    # Pull printer settings
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
        return jsonify({'error': f'Invalid printer config: {e}'}), 500

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
        return jsonify({
            'ok': True, 
            'elapsed_sec': round(elapsed_sec, 3),
            'method': 'direct_image_printing'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete', methods=['POST'])
def api_delete():
    """Move a past image to recent/deleted/{same folder structure}."""
    data = request.get_json(silent=True) or {}
    rel = data.get('path')
    if not rel:
        return jsonify({'error': 'Missing path'}), 400
    p = _safe_path_from_query(rel)
    if not p:
        return jsonify({'error': 'Invalid path'}), 400

    base = Path(os.path.dirname(__file__))
    try:
        # Compute path relative to recent root; if coming from logs, map logs/.. to recent/..
        past_root = _past_images_dir()
        logs_root = _logs_dir()
        if str(p).startswith(str(past_root.resolve())):
            rel_to_root = p.resolve().relative_to(past_root.resolve())
        elif str(p).startswith(str(logs_root.resolve())):
            rel_to_root = p.resolve().relative_to(logs_root.resolve())
        else:
            return jsonify({'error': 'Path not under expected roots'}), 400

        deleted_root = past_root / 'deleted'
        dest_dir = deleted_root / rel_to_root.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / p.name

        # Move the file
        p.rename(dest_path)
        
        # Also move the associated request.json file if it exists
        request_file = p.with_name('request.json')
        if request_file.is_file():
            try:
                request_dest = dest_path.with_name('request.json')
                request_file.rename(request_dest)
            except Exception:
                pass  # Don't fail if we can't move the request file
        
        # Also move metrics.json if it exists
        metrics_file = p.with_name('metrics.json')
        if metrics_file.is_file():
            try:
                metrics_dest = dest_path.with_name('metrics.json')
                metrics_file.rename(metrics_dest)
            except Exception:
                pass  # Don't fail if we can't move the metrics file
        
        return jsonify({'ok': True, 'deleted_to': str(dest_path.relative_to(base)).replace('\\','/')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/preview.png', methods=['GET'])
def latest_preview_png():
    """Serve the most recent label preview PNG."""
    p = _find_latest_preview()
    if not p:
        return Response("Preview not found", mimetype='text/plain'), 404
    # Add a cache-busting header-friendly timestamp
    resp = send_file(str(p), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/upload', methods=['POST'])
def upload_image_file():
    """Handles image file uploads from the user."""
    if 'imageFile' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['imageFile']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # --- Server-Side Validation ---
    if file and allowed_file(file.filename):
        # Sanitize the filename to prevent security issues (e.g., ../../)
        filename = secure_filename(file.filename)
        
        # Ensure the upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save the file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Return a success response with the path to the file
        # The frontend will use this path for the `-i` argument
        return jsonify({
            'message': f'File "{filename}" uploaded successfully!',
            'filePath': filepath
        }), 200
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PNG, JPG, or GIF.'}), 400


def build_command_from_payload(payload: dict):
    """Build command list for pi-label-printer.py based on provided payload."""
    script_path = os.path.join(os.path.dirname(__file__), 'pi-label-printer.py')
    cmd = [sys.executable or 'python3', script_path]

    # Booleans
    if payload.get('list') is True:
        cmd.append('-l')
    if payload.get('show_date') is True:
        cmd.append('-o')
    if payload.get('preview_only') is True:
        cmd.append('-p')

    # Integers
    count = payload.get('count')
    if count is not None:
        try:
            count_val = int(count)
            if count_val > 0:
                cmd.extend(['-c', str(count_val)])
        except (TypeError, ValueError):
            pass

    # Strings
    mapping = [
        ('date', '-d'),
        ('message', '-m'),
        ('border_message', '-b'),
        ('side_border', '-s'),
        ('image', '-i'),
    ]
    for key, flag in mapping:
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            cmd.extend([flag, val.strip()])

    return cmd


def validate_payload(payload: dict):
    """Validate incoming POST data. Returns (ok: bool, errors: list[str])."""
    errors = []

    # count: positive integer if provided
    if 'count' in payload and payload['count'] is not None:
        try:
            count_val = int(payload['count'])
            if count_val <= 0:
                errors.append("'count' must be a positive integer")
        except (TypeError, ValueError):
            errors.append("'count' must be an integer")

    # date: YYYY-MM-DD if provided
    date_val = payload.get('date')
    if date_val:
        if not isinstance(date_val, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_val):
            errors.append("'date' must be in YYYY-MM-DD format")
        else:
            try:
                datetime.strptime(date_val, "%Y-%m-%d")
            except ValueError:
                errors.append("'date' is not a valid calendar date")

    # image: must exist if provided
    img = payload.get('image')
    if img:
        # <-- MODIFIED: Check if path exists. Path can now be in 'uploads/'
        # The frontend is responsible for providing a valid path from the upload response.
        # This server-side check ensures the file is actually there.
        base_path = Path(os.path.dirname(__file__))
        if not isinstance(img, str) or not (base_path / img).is_file():
            errors.append(f"'image' path does not exist on server: {html.escape(img)}")

    return (len(errors) == 0, errors)


@app.route('/api/pi-label/print', methods=['POST'])
def post_pi_label_print():
    """Trigger printing via pi-label-printer.py with provided options (JSON body)."""
    data = request.get_json(silent=True) or {}

    # Validate payload
    ok, errors = validate_payload(data)
    if not ok:
        return jsonify({'errors': errors}), 400

    # Check if we already have this template - if so, update existing instead of creating duplicate
    existing_match = _find_existing_template_match(data)
    if existing_match:
        # Update the existing template with new request, preserving the existing image
        _save_request_data(existing_match, data)
        
        # Touch the file to update its timestamp so it appears at the top of recent
        import os
        os.utime(existing_match, None)
        ts = int(existing_match.stat().st_mtime)
        preview_url = f"/preview.png?ts={ts}"
        
        return jsonify({
            'command': [],
            'returncode': 0,
            'stdout': 'Reusing existing template',
            'stderr': '',
            'elapsed_sec': 0.001,
            'preview_url': preview_url,
            'metrics': None,
            'template_reused': True
        }), 200

    cmd = build_command_from_payload(data)

    try:
        t0 = time.perf_counter()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed_sec = time.perf_counter() - t0

        # Find the latest preview if generated
        preview_path = _find_latest_preview()
        preview_url = None
        if preview_path:
            ts = int(preview_path.stat().st_mtime)
            preview_url = f"/preview.png?ts={ts}"
            
            # Save request data to logs (write-once) and mirror to recent
            logs_root = _logs_dir()
            if str(preview_path).startswith(str(logs_root)):
                # Save to logs directory (the source)
                _save_request_data(preview_path, data)
                # Mirror to recent
                _mirror_request_data_to_past_images(preview_path)
            else:
                # If preview is already in recent, save there directly
                _save_request_data(preview_path, data)

        metrics = _parse_metrics_from_stdout(result.stdout) or _find_latest_metrics()

        response = {
            'command': cmd,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'elapsed_sec': round(elapsed_sec, 3),
            'preview_url': preview_url,
            'metrics': metrics,
            'template_reused': False
        }
        status = 200 if result.returncode == 0 else 500
        return jsonify(response), status
    except FileNotFoundError:
        return jsonify({'error': 'pi-label-printer.py not found', 'command': cmd}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/app', methods=['GET'])
@app.route('/app/', methods=['GET'])
def app_index():
    """Serve the index HTML that includes the print form and links."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), "www"), "index.html")


@app.route('/recent', methods=['GET'])
def recent_page():
    """Serve the recent labels gallery."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), "www"), "recent.html")


@app.route('/app/date', methods=['GET'])
def app_date_print():
    """Run pi-label-printer.py with default options (today's date) and show result."""
    script_path = os.path.join(os.path.dirname(__file__), 'pi-label-printer.py')
    cmd = [sys.executable or 'python3', script_path, '-o']
    try:
        t0 = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        elapsed_sec = time.perf_counter() - t0
        # Discover preview if available
        preview_path = _find_latest_preview()
        preview_html = ""
        if preview_path:
            ts = int(preview_path.stat().st_mtime)
            preview_html = f"<h2>Preview</h2><img src='/preview.png?ts={ts}' alt='label preview' style='border:1px solid #ddd; max-width:600px;' />"
        ok = result.returncode == 0
        status = 'OK' if ok else 'Error'
        color = '#0a7d29' if ok else '#b00020'
        body = f"""
        <!doctype html>
        <meta charset='utf-8' />
        <title>Pi Label Printer — /app/date</title>
        <style>
          body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif; margin: 24px; }}
          .status {{ color: {color}; font-weight: 600; }}
          pre {{ background: #f6f8fa; padding: 12px; border-radius: 6px; }}
          a {{ color: #0366d6; text-decoration: none; }}
        </style>
        <h1>Print Today's Date</h1>
        <div class='status'>{status}: ran pi-label-printer.py (elapsed {elapsed_sec:.3f}s)</div>
        <h2>Command</h2>
        <pre>{html.escape(' '.join(cmd))}</pre>
        <h2>stdout</h2>
        <pre>{html.escape(result.stdout)}</pre>
        <h2>stderr</h2>
        <pre>{html.escape(result.stderr)}</pre>
        {preview_html}
        <p><a href='/app'>Back to index</a></p>
        """
        return Response(body, mimetype='text/html'), (200 if ok else 500)
    except FileNotFoundError:
        return Response("pi-label-printer.py not found", mimetype='text/plain'), 500
    except Exception as e:
        return Response(str(e), mimetype='text/plain'), 500


if __name__ == "__main__":
    # Simple dev server for local testing
    # <-- ADDED: Ensure upload folder exists on startup -->
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False)