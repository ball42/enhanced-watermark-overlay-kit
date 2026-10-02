"""
Flask application factory for EWOK
Following the application factory pattern for better modularity
"""

import logging
import os

from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def create_app(config_name=None):
    """Create and configure Flask app"""
    app = Flask(__name__)

    # Load configuration
    import config
    app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['DEBUG'] = config.DEBUG
    app.config['SECRET_KEY'] = config.SECRET_KEY

    # Ensure upload and temp directories exist
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.TEMP_FOLDER, exist_ok=True)

    # Register blueprints
    from views.main import main_bp
    from views.api import api_bp
    from views.template_api import template_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(template_bp)

    # Periodic cleanup of old temp files
    from utils.cleanup import cleanup_old_files

    # EWOK has no login, so it only answers to its own address: a foreign
    # Host header (DNS rebinding) or a cross-site write is refused.
    from flask import abort, request

    LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}

    @app.before_request
    def local_only():
        host = request.host.rsplit(":", 1)[0] if not request.host.startswith("[") else request.host.split("]")[0] + "]"
        if host not in LOCAL_HOSTS:
            abort(403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            site = request.headers.get("Sec-Fetch-Site")
            if site not in (None, "same-origin", "none"):
                abort(403)

    @app.before_request
    def run_cleanup():
        cleanup_old_files(config.TEMP_FOLDER, config.UPLOAD_FOLDER)

    return app