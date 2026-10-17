from flask import Blueprint, current_app, request, jsonify, send_file
import os
import re
import uuid
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance, ImageFilter

from config import ALLOWED_EXTENSIONS, WALLPAPER_PRESETS
from utils.image_processing import (
    resize_for_wallpaper, optimize_wallpaper_size,
    add_text_overlays, add_image_overlays,
    add_background, add_watermark
)

api_bp = Blueprint('api', __name__, url_prefix='/api')

MAX_PHOTO_PIXELS = 40_000_000  # same budget as wallrender's canvas
RESIZE_RANGE = (10, 400)  # percent, as the slider offers

# Upload names are "<uuid4>_<name>" (upload_file below).
UPLOAD_NAME = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_')
EXPIRED = 'This upload expired after an hour without use. Upload it again.'


def upload_folder():
    """The app's upload folder, read per request (tests give each app its own)."""
    return current_app.config['UPLOAD_FOLDER']


def temp_folder():
    """The app's folder for processed results, read per request."""
    return current_app.config['TEMP_FOLDER']


def mark_used(path):
    """Refresh a file's mtime: cleanup removes files an hour after their last use."""
    try:
        os.utime(path)
    except OSError:
        pass

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_filepath(filename, base_folder):
    """Prevent path traversal by constraining file to base_folder"""
    safe_name = os.path.basename(filename)
    full_path = os.path.realpath(os.path.join(base_folder, safe_name))
    real_base = os.path.realpath(base_folder)
    if not full_path.startswith(real_base + os.sep) and full_path != real_base:
        return None
    return full_path

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(upload_folder(), unique_filename)
        file.save(filepath)
        
        # Get image dimensions, and refuse what is not an image or too big
        try:
            with Image.open(filepath) as img:
                width, height = img.size
        except (OSError, Image.DecompressionBombError):
            os.remove(filepath)
            return jsonify({'error': 'That file is not a readable image.'}), 400
        if width * height > MAX_PHOTO_PIXELS:
            os.remove(filepath)
            return jsonify({'error': 'That image is too large (40 megapixels at most).'}), 400
        
        return jsonify({
            'success': True,
            'filename': unique_filename,
            'dimensions': {'width': width, 'height': height}
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

def remove_previous_result(previous, output_path):
    """Delete the result a new render replaces: only a processed_ file in the temp folder."""
    if not isinstance(previous, str) or not os.path.basename(previous).startswith('processed_'):
        return
    path = safe_filepath(previous, temp_folder())
    if not path or path == os.path.realpath(output_path):
        return
    try:
        os.remove(path)
    except OSError:
        pass  # already gone (cleanup, or a second tab)


@api_bp.route('/process', methods=['POST'])
def process_image():
    """Process image with applied effects"""
    data = request.get_json()
    
    if not data or 'filename' not in data:
        return jsonify({'error': 'No filename provided'}), 400
    
    input_path = safe_filepath(data['filename'], upload_folder())
    if not input_path or not os.path.exists(input_path):
        if UPLOAD_NAME.match(os.path.basename(str(data['filename']))):
            return jsonify({'error': EXPIRED}), 410
        return jsonify({'error': 'File not found'}), 404
    mark_used(input_path)
    for overlay in data.get('image_overlays') or []:
        if isinstance(overlay, dict) and isinstance(overlay.get('filename'), str):
            overlay_path = safe_filepath(overlay['filename'], upload_folder())
            if overlay_path and os.path.exists(overlay_path):
                mark_used(overlay_path)
    
    warnings = []  # problems the user should see, e.g. a skipped overlay
    try:
        with Image.open(input_path) as base_img:
            # Convert to RGBA for transparency support
            if base_img.mode != 'RGBA':
                base_img = base_img.convert('RGBA')
            
            result_img = base_img.copy()
            
            # Apply opacity (transparency)
            if 'opacity' in data and data['opacity'] != 100:
                opacity = data['opacity'] / 100.0
                if result_img.mode != 'RGBA':
                    result_img = result_img.convert('RGBA')
                
                # Create new alpha channel based on opacity
                alpha = result_img.split()[-1]  # Get current alpha channel
                alpha = alpha.point(lambda p: int(p * opacity))  # Scale alpha values
                result_img.putalpha(alpha)
            
            # Apply saturation (color intensity)
            if 'saturation' in data and data['saturation'] != 100:
                saturation = data['saturation'] / 100.0
                enhancer = ImageEnhance.Color(result_img)
                result_img = enhancer.enhance(saturation)
            
            # Apply brightness
            if 'brightness' in data and data['brightness'] != 100:
                enhancer = ImageEnhance.Brightness(result_img)
                result_img = enhancer.enhance(data['brightness'] / 100.0)

            # Apply contrast
            if 'contrast' in data and data['contrast'] != 100:
                enhancer = ImageEnhance.Contrast(result_img)
                result_img = enhancer.enhance(data['contrast'] / 100.0)

            # Apply blur/sharpen (0-100, 50=neutral)
            if 'blur_sharpen' in data and data['blur_sharpen'] != 50:
                bs = data['blur_sharpen']
                if bs < 50:
                    radius = (50 - bs) / 5.0
                    result_img = result_img.filter(ImageFilter.GaussianBlur(radius=radius))
                else:
                    sharpener = ImageEnhance.Sharpness(result_img)
                    result_img = sharpener.enhance(1.0 + (bs - 50) / 50.0 * 3.0)

            # Apply rotation
            if 'rotation' in data and data['rotation'] != 0:
                result_img = result_img.rotate(data['rotation'], resample=Image.Resampling.BICUBIC,
                                               expand=True, fillcolor=(0, 0, 0, 0))

            # Apply custom resize
            if 'resize' in data and data['resize'] != 100:
                resize = data['resize']
                if isinstance(resize, bool) or not isinstance(resize, (int, float)):
                    return jsonify({'error': 'Resize must be a number.'}), 400
                resize = min(max(resize, RESIZE_RANGE[0]), RESIZE_RANGE[1])
                resize_factor = resize / 100.0
                if result_img.width * result_img.height * resize_factor ** 2 > MAX_PHOTO_PIXELS:
                    return jsonify({'error': 'That resize would exceed 40 megapixels.'}), 400
                new_width = int(result_img.width * resize_factor)
                new_height = int(result_img.height * resize_factor)
                result_img = result_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Resize for wallpaper mode
            if data.get('wallpaper_mode') and data.get('wallpaper_preset'):
                preset_name = data['wallpaper_preset']
                if preset_name in WALLPAPER_PRESETS:
                    if preset_name == 'Optimized':
                        # For optimized mode, calculate best size based on original dimensions
                        result_img = optimize_wallpaper_size(result_img)
                    else:
                        target_size = WALLPAPER_PRESETS[preset_name]
                        result_img = resize_for_wallpaper(result_img, target_size, data.get('fit_mode', 'fit'))
            
            # Add text overlays
            if 'text_overlays' in data:
                result_img = add_text_overlays(result_img, data['text_overlays'])
            
            # Add image overlays
            if 'image_overlays' in data:
                result_img = add_image_overlays(result_img, data['image_overlays'], upload_folder(),
                                                warnings=warnings)
            
            # Add background
            if 'background' in data and data['background']:
                result_img = add_background(result_img, data['background'])
            
            # Add watermark
            if 'watermark' in data:
                result_img = add_watermark(result_img, data['watermark'])
            
            # Determine output format
            output_format = data.get('output_format', 'png').lower()
            format_map = {
                'png': ('PNG', '.png'),
                'jpeg': ('JPEG', '.jpg'),
                'webp': ('WEBP', '.webp'),
            }
            pil_format, ext = format_map.get(output_format, ('PNG', '.png'))

            output_filename = f"processed_{uuid.uuid4()}{ext}"
            output_path = os.path.join(temp_folder(), output_filename)

            # JPEG doesn't support alpha — convert to RGB
            if pil_format == 'JPEG':
                if result_img.mode == 'RGBA':
                    bg = Image.new('RGB', result_img.size, (255, 255, 255))
                    bg.paste(result_img, mask=result_img.split()[3])
                    result_img = bg
                result_img.save(output_path, pil_format, quality=95)
            elif pil_format == 'WEBP':
                result_img.save(output_path, pil_format, quality=90)
            else:
                result_img.save(output_path, pil_format)
            remove_previous_result(data.get('previous_filename'), output_path)

            return jsonify({
                'success': True,
                'processed_filename': output_filename,
                'warnings': warnings,
                'dimensions': {'width': result_img.width, 'height': result_img.height}
            })
            
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@api_bp.route('/download/<filename>')
def download_file(filename):
    """Download processed image file"""
    filepath = safe_filepath(filename, temp_folder())
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    mark_used(filepath)
    return send_file(filepath, as_attachment=True, download_name=f"edited_{filename}")

@api_bp.route('/preview/<filename>')
def preview_file(filename):
    """Preview processed image file"""
    filepath = safe_filepath(filename, temp_folder())
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    mark_used(filepath)
    return send_file(filepath)

@api_bp.route('/original/<filename>')
def preview_original(filename):
    """Preview original uploaded image file"""
    filepath = safe_filepath(filename, upload_folder())
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    mark_used(filepath)
    return send_file(filepath)