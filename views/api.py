from flask import Blueprint, request, jsonify, send_file
import os
import uuid
import sys
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import UPLOAD_FOLDER, TEMP_FOLDER, ALLOWED_EXTENSIONS, WALLPAPER_PRESETS
from utils.image_processing import (
    resize_for_wallpaper, optimize_wallpaper_size, 
    add_text_overlays, add_image_overlays, 
    add_background, add_watermark
)

api_bp = Blueprint('api', __name__, url_prefix='/api')

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        # Get image dimensions
        with Image.open(filepath) as img:
            width, height = img.size
        
        return jsonify({
            'success': True,
            'filename': unique_filename,
            'dimensions': {'width': width, 'height': height}
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@api_bp.route('/process', methods=['POST'])
def process_image():
    """Process image with applied effects"""
    data = request.get_json()
    
    if not data or 'filename' not in data:
        return jsonify({'error': 'No filename provided'}), 400
    
    input_path = os.path.join(UPLOAD_FOLDER, data['filename'])
    if not os.path.exists(input_path):
        return jsonify({'error': 'File not found'}), 404
    
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
            
            # Apply custom resize
            if 'resize' in data and data['resize'] != 100:
                resize_factor = data['resize'] / 100.0
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
                result_img = add_image_overlays(result_img, data['image_overlays'], UPLOAD_FOLDER)
            
            # Add background
            if 'background' in data and data['background']:
                result_img = add_background(result_img, data['background'])
            
            # Add watermark
            if 'watermark' in data:
                result_img = add_watermark(result_img, data['watermark'])
            
            # Save processed image
            output_filename = f"processed_{uuid.uuid4()}.png"
            output_path = os.path.join(TEMP_FOLDER, output_filename)
            result_img.save(output_path, 'PNG')
            
            return jsonify({
                'success': True,
                'processed_filename': output_filename,
                'dimensions': {'width': result_img.width, 'height': result_img.height}
            })
            
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@api_bp.route('/download/<filename>')
def download_file(filename):
    """Download processed image file"""
    filepath = os.path.join(TEMP_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=f"edited_{filename}")
    return jsonify({'error': 'File not found'}), 404

@api_bp.route('/preview/<filename>')
def preview_file(filename):
    """Preview processed image file"""
    filepath = os.path.join(TEMP_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return jsonify({'error': 'File not found'}), 404

@api_bp.route('/original/<filename>')
def preview_original(filename):
    """Preview original uploaded image file"""
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return jsonify({'error': 'File not found'}), 404