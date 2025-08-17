from __future__ import annotations

import os
from pathlib import Path
from flask import Blueprint, send_from_directory, request

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WWW_DIR = BASE_DIR / 'www'

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/', methods=['GET'])
@pages_bp.route('/index.html', methods=['GET'])
@pages_bp.route('/app', methods=['GET'])
@pages_bp.route('/app/', methods=['GET'])
@pages_bp.route('/app/pi-label', methods=['GET'])
@pages_bp.route('/recent', methods=['GET'])
def serve_pages():
    # Map all these routes to index.html or recent.html accordingly
    if str(request.path).startswith('/recent'):
        return send_from_directory(os.path.join(BASE_DIR, 'www'), 'recent.html')
    return send_from_directory(os.path.join(BASE_DIR, 'www'), 'index.html')


@pages_bp.route('/<path:filename>')
def serve_static_files(filename: str):
    """Serve any static file from the 'www' directory."""
    return send_from_directory(os.path.join(BASE_DIR, 'www'), filename)
