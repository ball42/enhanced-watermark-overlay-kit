from flask import Blueprint, render_template

from config import BRANDER_VARIABLES, SAMPLE_DEVICES, TEMPLATE_CANVASES, WALLPAPER_PRESETS
from wallrender.devices import device_profiles

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main page with image editor interface"""
    return render_template('index.html', wallpaper_presets=WALLPAPER_PRESETS)


@main_bp.route('/template')
def template_editor():
    """Template mode: design a Brander wallpaper template"""
    return render_template('template.html', variables=BRANDER_VARIABLES,
                           canvases=TEMPLATE_CANVASES, sample_devices=SAMPLE_DEVICES,
                           device_profiles=device_profiles())
