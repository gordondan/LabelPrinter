from __future__ import annotations

import logging
from pathlib import Path
from flask import Flask
import threading

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
    # Start background job queue (single-worker to avoid memory pressure)
    try:
        from .services.jobs import JobQueue
        app.job_queue = JobQueue(max_concurrent=1)  # type: ignore[attr-defined]
        app.job_queue.start()       # type: ignore[attr-defined]
    except Exception as e:
        app.logger.warning("Job queue not started: %s", e)
    # Pre-generate today's label in the background so the home button can use it without triggering generation
    try:
        from .services.today_label import ensure_today_label
        def _bg_ensure():
            try:
                ensure_today_label(logger=app.logger, force=False)
            except Exception:
                pass
        threading.Thread(target=_bg_ensure, name='ensure-today', daemon=True).start()
    except Exception:
        pass

    # GPIO listener moved to a feature module and disabled by default.
    # To enable, a separate bootstrap can import services.gpio_listener and start it conditionally.

    return app
