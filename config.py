"""
Configuration settings for EWOK
"""

import os

# File upload settings
UPLOAD_FOLDER = 'static/uploads'
TEMP_FOLDER = 'temp'
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

# Flask app settings
DEBUG = True
SECRET_KEY = os.environ.get('SECRET_KEY', 'ewok-development-key-change-if-in-production')