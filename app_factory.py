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

STATIC_MAX_AGE = 24 * 3600  # seconds; a versioned static file never changes under its URL


def create_app(config_name=None):
    """Create and configure Flask app"""
    app = Flask(__name__)

    # Load configuration
    import config
    app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
    app.config['TEMP_FOLDER'] = config.TEMP_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['DEBUG'] = config.DEBUG
    app.config['SECRET_KEY'] = config.SECRET_KEY

    # Ensure upload and temp directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

    # Register blueprints
    from views.main import main_bp
    from views.api import api_bp
    from views.template_api import template_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(template_bp)

    # Every page reads errors as JSON; Flask's own 413 page is HTML.
    from flask import jsonify, request

    @app.errorhandler(413)
    def too_large(_err):
        mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        return jsonify(error=f"That file is larger than {mb} MB."), 413

    # The pages read /api/ errors as JSON, so these answers are JSON there
    # too; other paths keep Flask's HTML pages.
    API_ERRORS = {
        403: "EWOK refuses requests from other sites and other computers.",
        404: "EWOK has no such item.",
        405: "EWOK does not accept that method here.",
    }

    def api_error(err):
        if request.path.startswith("/api/"):
            return jsonify(error=API_ERRORS[err.code]), err.code
        return err

    for code in API_ERRORS:
        app.register_error_handler(code, api_error)

    # Static files: the pages name each one with a hash of its bytes
    # (?v=...), so it can be cached for a day and a changed file still
    # shows at once. A request without the hash keeps Flask's no-cache.
    import hashlib

    static_hashes = {}

    def static_v(path):
        full = os.path.join(app.static_folder, path)
        stat = os.stat(full)
        key = (path, stat.st_mtime_ns, stat.st_size)
        if key not in static_hashes:
            with open(full, "rb") as fh:
                static_hashes[key] = hashlib.sha256(fh.read()).hexdigest()[:12]
        return f"/static/{path}?v={static_hashes[key]}"

    app.jinja_env.globals["static_v"] = static_v

    @app.after_request
    def cache_versioned_static(response):
        if request.endpoint == "static" and request.args.get("v") and response.status_code == 200:
            response.cache_control.no_cache = None
            response.cache_control.public = True
            response.cache_control.max_age = STATIC_MAX_AGE
        return response

    # Periodic cleanup of old temp files
    from utils.cleanup import cleanup_old_files

    # EWOK has no login, so it only answers to its own address: a foreign
    # Host header (DNS rebinding) or a cross-site write is refused.
    from flask import abort

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

    # No other site may frame EWOK's pages: inside a frame, a tricked click
    # would be a same-origin request and pass the check above.
    @app.after_request
    def no_framing(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.before_request
    def run_cleanup():
        # The same folders the routes in views/api.py use.
        cleanup_old_files(app.config['TEMP_FOLDER'], app.config['UPLOAD_FOLDER'])

    return app