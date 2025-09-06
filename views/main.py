from flask import Blueprint, render_template
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import WALLPAPER_PRESETS

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main page with image editor interface"""
    return render_template('index.html', wallpaper_presets=WALLPAPER_PRESETS)