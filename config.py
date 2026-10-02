"""
Configuration settings for EWOK
"""

import logging
import os
import secrets

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File upload settings (absolute, so they do not depend on the cwd)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
TEMP_FOLDER = os.path.join(BASE_DIR, 'temp')
# Template mode's asset library (backgrounds, logos): kept, not cleaned up
TEMPLATE_ASSETS_FOLDER = os.path.join(BASE_DIR, 'template_assets')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Wallpaper presets for common devices
WALLPAPER_PRESETS = {
    'iPhone 15 Pro': (1179, 2556),
    'iPhone 15': (1179, 2556),
    'iPhone 14 Pro': (1179, 2556),
    'iPhone 14': (1170, 2532),
    'iPad Pro 12.9"': (2048, 2732),
    'iPad Air': (1620, 2160),
    'iPad': (1620, 2160),
    'MacBook Air 13"': (2560, 1600),
    'MacBook Pro 14"': (3024, 1964),
    'MacBook Pro 16"': (3456, 2234),
    'iMac 24"': (4480, 2520),
    'Studio Display': (5120, 2880),
    'Pro Display XDR': (6016, 3384),
    'Custom 16:9 1080p': (1920, 1080),
    'Custom 16:9 4K': (3840, 2160),
    'Custom 4:3': (1024, 768),
    'Custom Square': (1080, 1080),
    'Optimized': 'auto'  # Special case for optimized sizing
}

# Template mode: values Brander can print (its allowlist), and canvas presets.
BRANDER_VARIABLES = ['device_name', 'serial_number', 'asset_tag', 'jss_id', 'location.building']
TEMPLATE_CANVASES = {
    'iPhone (portrait)': (1290, 2796),
    'iPad (square, both orientations)': (2732, 2732),
    'iPad Pro 12.9" (portrait)': (2048, 2732),
}

# Sample devices for the template preview: the shape Brander's
# build_values() produces from a verified Jamf record (user.* only when
# both the template and the admin allow personal fields).
SAMPLE_DEVICES = [
    {'name': 'iPhone', 'values': {
        'device_name': 'Front Desk iPhone', 'serial_number': 'F9FXK2Q1N72Q',
        'asset_tag': 'HR-0042', 'jss_id': 42, 'location': {'building': 'North Campus'},
        'user': {'username': 'jdoe', 'real_name': 'Jordan Doe', 'email': 'jordan.doe@example.org'}}},
    {'name': 'iPad', 'values': {
        'device_name': 'Ward 3 iPad', 'serial_number': 'DMPX1234ABCD',
        'asset_tag': 'NUR-0317', 'jss_id': 317, 'location': {'building': 'Main Hospital'},
        'user': {'username': 'nurse.station3', 'real_name': 'Ward 3 Nurses', 'email': 'ward3@example.org'}}},
    {'name': 'No asset tag, no building', 'values': {
        'device_name': 'ControlPad', 'serial_number': 'T9T0377WR6',
        'asset_tag': '', 'jss_id': 12, 'location': {'building': ''}}},
]

# Flask app settings
# Local tool: debug (and its interactive debugger) only when asked for.
DEBUG = os.environ.get('EWOK_DEBUG', '').lower() in ('1', 'true', 'yes')
HOST = '127.0.0.1'
PORT = int(os.environ.get('EWOK_PORT', '5055'))  # 5000 is macOS AirPlay
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("SECRET_KEY not set — using random key. Sessions will not persist across restarts.")