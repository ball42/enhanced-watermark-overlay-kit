"""
EWOK - Enhanced Watermark Overlay Kit
Main application entry point
"""

from app_factory import create_app

# Create Flask app using the factory pattern
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)