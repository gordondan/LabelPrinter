from __future__ import annotations

import logging
from pathlib import Path
from flask import Flask

BASE_DIR = Path(__file__).resolve().parent.parent  # project root


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)  # we serve static via routes

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )
    app.logger.setLevel(logging.INFO)

    # Config
    app.config.setdefault('UPLOAD_FOLDER', 'uploads')
    app.config.setdefault('SECRET_KEY', 'a-super-secret-key-for-sessions')

    # Ensure upload folder exists
    (BASE_DIR / app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from .routes.pages import pages_bp
    from .routes.api import api_bp
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix='')

    return app
