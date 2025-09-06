"""
Flask application factory for EWOK
Following the application factory pattern for better modularity
"""

import os
from flask import Flask
from flask_cors import CORS

def create_app(config_name=None):
    """Create and configure Flask app"""
    app = Flask(__name__)
    CORS(app)
    
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
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    
    return app