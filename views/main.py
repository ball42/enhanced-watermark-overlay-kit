from flask import Blueprint, render_template

from config import WALLPAPER_PRESETS

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main page with image editor interface"""
    return render_template('index.html', wallpaper_presets=WALLPAPER_PRESETS)