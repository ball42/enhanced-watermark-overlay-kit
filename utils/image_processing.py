"""
Image processing utilities for EWOK
Handles all image manipulation operations including resizing, overlays, backgrounds, and watermarks
"""

import logging
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageChops

logger = logging.getLogger(__name__)

_HEX_PATTERN = re.compile(r'^#?([0-9a-fA-F]{6})$')


def hex_to_rgb(hex_color):
    """Convert hex color string to RGB tuple with validation.
    Returns (0, 0, 0) for invalid input."""
    if not isinstance(hex_color, str):
        return (0, 0, 0)
    match = _HEX_PATTERN.match(hex_color.strip())
    if not match:
        return (0, 0, 0)
    h = match.group(1)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


FONT_MAP = {
    'Arial': ['Arial.ttf', '/System/Library/Fonts/Arial.ttf'],
    'Times New Roman': ['Times New Roman.ttf', '/System/Library/Fonts/Supplemental/Times New Roman.ttf'],
    'Courier New': ['Courier New.ttf', '/System/Library/Fonts/Supplemental/Courier New.ttf'],
    'Georgia': ['Georgia.ttf', '/System/Library/Fonts/Supplemental/Georgia.ttf'],
    'Verdana': ['Verdana.ttf', '/System/Library/Fonts/Supplemental/Verdana.ttf'],
    'Impact': ['Impact.ttf', '/System/Library/Fonts/Supplemental/Impact.ttf'],
    'Comic Sans MS': ['Comic Sans MS.ttf', '/System/Library/Fonts/Supplemental/Comic Sans MS.ttf'],
}


def load_font(size, family=None):
    """Load a font with system fallbacks. Optionally specify a font family."""
    if family and family in FONT_MAP:
        for path in FONT_MAP[family]:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Default fallback chain
    try:
        return ImageFont.truetype("Arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/System/Library/Fonts/Arial.ttf", size)
        except Exception:
            # Pillow's scalable built-in font, so the size is still honoured.
            return ImageFont.load_default(size=size)


def optimize_wallpaper_size(img):
    """Optimize image size for common wallpaper use while maintaining quality"""
    width, height = img.size
    
    # Calculate aspect ratio
    aspect_ratio = width / height
    
    # Common wallpaper optimization targets
    if aspect_ratio > 1.5:  # Wide/landscape
        # Optimize for desktop use
        if width > 2560:
            new_width = 2560
            new_height = int(new_width / aspect_ratio)
        else:
            return img  # Already optimized
    elif aspect_ratio < 0.8:  # Portrait (mobile)
        # Optimize for mobile use
        if height > 2560:
            new_height = 2560
            new_width = int(new_height * aspect_ratio)
        else:
            return img  # Already optimized
    else:  # Square-ish
        # Optimize for general use
        max_dim = max(width, height)
        if max_dim > 1920:
            scale_factor = 1920 / max_dim
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
        else:
            return img  # Already optimized
    
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def resize_for_wallpaper(img, target_size, fit_mode='fit'):
    """Resize image for wallpaper with different fit modes"""
    target_width, target_height = target_size
    
    if fit_mode == 'stretch':
        return img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    elif fit_mode == 'crop':
        # Scale and crop to fill
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            # Image is wider, crop sides
            new_height = target_height
            new_width = int(new_height * img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - target_width) // 2
            img = img.crop((left, 0, left + target_width, target_height))
        else:
            # Image is taller, crop top/bottom
            new_width = target_width
            new_height = int(new_width / img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            top = (new_height - target_height) // 2
            img = img.crop((0, top, target_width, top + target_height))
        
        return img
    
    else:  # fit mode
        # Scale to fit within bounds
        img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Create new image with target size and paste centered
        result = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
        x = (target_width - img.width) // 2
        y = (target_height - img.height) // 2
        result.paste(img, (x, y))
        
        return result


def _draw_text_with_effects(draw, pos_x, pos_y, text, font, color, effect, effect_color, effect_strength):
    """Draw text with optional effects (shadow, outline, glow) onto a draw context."""
    if effect == 'shadow':
        shadow_offset = effect_strength
        draw.text((pos_x + shadow_offset, pos_y + shadow_offset), text, fill=effect_color, font=font)
    elif effect == 'outline':
        stroke_width = effect_strength
        for adj in range(-stroke_width, stroke_width + 1):
            for adj2 in range(-stroke_width, stroke_width + 1):
                if adj != 0 or adj2 != 0:
                    draw.text((pos_x + adj, pos_y + adj2), text, fill=effect_color, font=font)
    elif effect == 'glow':
        glow_radius = effect_strength * 2
        for radius in range(glow_radius, 0, -1):
            alpha = int(255 * (1 - radius / glow_radius) * 0.3)
            glow_color_with_alpha = effect_color + format(alpha, '02X')
            for angle in range(0, 360, 30):
                glow_x = pos_x + radius * math.cos(math.radians(angle))
                glow_y = pos_y + radius * math.sin(math.radians(angle))
                draw.text((glow_x, glow_y), text, fill=glow_color_with_alpha, font=font)

    # Draw main text on top
    draw.text((pos_x, pos_y), text, fill=color, font=font)


def parse_position(value, total, default=0):
    """A position or size in pixels: an int or float, or a string such as
    "25", "25px" or "12.5%" (of total). Anything else gives default."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip().lower()
        try:
            if text.endswith('%'):
                return int(float(text[:-1]) / 100 * total)
            if text.endswith('px'):
                text = text[:-2].strip()
            return int(float(text))
        except ValueError:
            return default
    return default


def add_text_overlays(img, text_overlays):
    """Add text overlays to image with alignment support and percentage-based sizing"""
    draw = ImageDraw.Draw(img)

    for overlay in text_overlays:
        text = overlay.get('text', '')
        if not text:
            continue

        x = overlay.get('x', 0)
        y = overlay.get('y', 0)

        # Handle percentage-based sizing (new) or absolute sizing (legacy)
        size_percent = overlay.get('size_percent')
        if size_percent:
            size = int(img.width * (size_percent / 100))
        else:
            size = overlay.get('size', 24)

        alignment = overlay.get('alignment', 'center')
        color = overlay.get('color', '#FFFFFF')
        text_effect = overlay.get('text_effect', 'none')
        effect_color = overlay.get('effect_color', '#000000')
        effect_strength = overlay.get('effect_strength', 3)
        font_family = overlay.get('font_family')
        text_opacity = overlay.get('text_opacity', 100)

        font = load_font(size, font_family)

        # Calculate text dimensions for alignment
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = parse_position(x, img.width, default=img.width // 2)
        y = parse_position(y, img.height, default=img.height // 2)

        # Apply alignment to x position
        if alignment == 'center':
            positioned_x = x - (text_width // 2)
        elif alignment == 'right':
            positioned_x = x - text_width
        else:  # left
            positioned_x = x

        positioned_y = y

        # Ensure text doesn't go off the edges
        positioned_x = max(0, min(positioned_x, img.width - text_width))
        positioned_y = max(0, min(positioned_y, img.height - text_height))

        if text_opacity < 100:
            # Draw on a temporary layer and apply opacity
            text_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            _draw_text_with_effects(text_draw, positioned_x, positioned_y, text, font,
                                    color, text_effect, effect_color, effect_strength)
            alpha = text_layer.split()[-1]
            alpha = alpha.point(lambda p: int(p * (text_opacity / 100.0)))
            text_layer.putalpha(alpha)
            img = Image.alpha_composite(img, text_layer)
            draw = ImageDraw.Draw(img)
        else:
            _draw_text_with_effects(draw, positioned_x, positioned_y, text, font,
                                    color, text_effect, effect_color, effect_strength)

    return img


def add_image_overlays(img, image_overlays, upload_folder, warnings=None):
    """Add image overlays to main image. Problems are appended to warnings
    (when given) so the UI can say which overlay was skipped and why."""
    warnings = [] if warnings is None else warnings
    for overlay in image_overlays:
        name = os.path.basename(str(overlay.get('filename', '')))
        overlay_path = os.path.join(upload_folder, name)
        if not name or not os.path.isfile(overlay_path):
            warnings.append(f"Image overlay {name or '(none)'} was skipped: the file is not uploaded.")
            continue
            
        try:
            with Image.open(overlay_path) as overlay_img:
                if overlay_img.mode != 'RGBA':
                    overlay_img = overlay_img.convert('RGBA')
                
                # Resize overlay if specified (supports px integers or "%" strings)
                if 'width' in overlay or 'height' in overlay:
                    raw_w = overlay.get('width')
                    raw_h = overlay.get('height')
                    orig_w, orig_h = overlay_img.width, overlay_img.height

                    w = parse_position(raw_w, img.width, default=None) if raw_w is not None else None
                    h = parse_position(raw_h, img.height, default=None) if raw_h is not None else None

                    # Aspect-ratio preservation when only one dimension given
                    if w and not h:
                        h = int(orig_h * (w / orig_w))
                    elif h and not w:
                        w = int(orig_w * (h / orig_h))
                    elif not w and not h:
                        w, h = orig_w, orig_h

                    overlay_img = overlay_img.resize((w, h), Image.Resampling.LANCZOS)
                
                # Apply opacity
                if 'opacity' in overlay and overlay['opacity'] != 100:
                    alpha = overlay_img.split()[-1]
                    alpha = alpha.point(lambda p: int(p * (overlay['opacity'] / 100.0)))
                    overlay_img.putalpha(alpha)
                
                x = parse_position(overlay.get('x', 0), img.width)
                y = parse_position(overlay.get('y', 0), img.height)
                img.paste(overlay_img, (x, y), overlay_img)

        except Exception as e:
            logger.warning("Error adding overlay: %s", e)
            warnings.append(f"Image overlay {name} was skipped: {e}")
            continue
    
    return img


def add_background(img, background_config):
    """Add background to image"""
    bg_type = background_config.get('type', 'color')
    
    if bg_type == 'color':
        color = background_config.get('color', '#FFFFFF')
        rgb_color = hex_to_rgb(color)
        
        # Create background with same size as image
        background = Image.new('RGB', img.size, rgb_color)
        
        # If original image has transparency, paste it onto the background
        if img.mode == 'RGBA':
            background.paste(img, (0, 0), img)
            return background.convert('RGBA')
        else:
            # For non-transparent images, just return the original with background color applied
            background.paste(img, (0, 0))
            return background
            
    elif bg_type == 'gradient':
        start_color = background_config.get('start_color', '#FFFFFF')
        end_color = background_config.get('end_color', '#000000')
        direction = background_config.get('direction', 'vertical')

        start_rgb = hex_to_rgb(start_color)
        end_rgb = hex_to_rgb(end_color)
        
        # Built from Pillow's 256-step linear gradient: one resize, not a
        # putpixel per pixel.
        width, height = img.size
        vertical = Image.linear_gradient('L').resize((width, height))
        horizontal = Image.linear_gradient('L').rotate(90).resize((width, height))
        if direction == 'horizontal':
            mask = horizontal
        elif direction == 'diagonal':
            mask = ImageChops.add(horizontal, vertical, scale=2)
        else:
            mask = vertical
        background = Image.composite(Image.new('RGB', (width, height), end_rgb),
                                     Image.new('RGB', (width, height), start_rgb), mask)

        # Paste image onto gradient background
        if img.mode == 'RGBA':
            background.paste(img, (0, 0), img)
            return background.convert('RGBA')
        else:
            background.paste(img, (0, 0))
            return background
            
    elif bg_type == 'pattern':
        pattern_type = background_config.get('pattern', 'dots')
        color1 = background_config.get('color1', '#FFFFFF')
        color2 = background_config.get('color2', '#E0E0E0')

        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
        
        width, height = img.size
        background = Image.new('RGB', (width, height), rgb1)
        draw = ImageDraw.Draw(background)
        
        if pattern_type == 'dots':
            # Dot pattern
            dot_size = 20
            spacing = 40
            for x in range(0, width, spacing):
                for y in range(0, height, spacing):
                    draw.ellipse([x, y, x + dot_size, y + dot_size], fill=rgb2)
        elif pattern_type == 'stripes':
            # Stripe pattern
            stripe_width = 30
            for x in range(0, width, stripe_width * 2):
                draw.rectangle([x, 0, x + stripe_width, height], fill=rgb2)
        elif pattern_type == 'checker':
            # Checkerboard pattern
            square_size = 40
            for x in range(0, width, square_size):
                for y in range(0, height, square_size):
                    if (x // square_size + y // square_size) % 2:
                        draw.rectangle([x, y, x + square_size, y + square_size], fill=rgb2)
        elif pattern_type == 'starburst':
            center_spacing = 120  # Distance between starburst centers
            ray_count = 8  # Number of rays per starburst
            ray_length = 40
            
            # Create starbursts across the image
            for center_x in range(center_spacing // 2, width, center_spacing):
                for center_y in range(center_spacing // 2, height, center_spacing):
                    # Draw rays emanating from center point
                    for i in range(ray_count):
                        angle = (2 * math.pi * i) / ray_count
                        # Calculate end point of ray
                        end_x = center_x + ray_length * math.cos(angle)
                        end_y = center_y + ray_length * math.sin(angle)
                        
                        # Draw ray as a line with thickness
                        draw.line([center_x, center_y, end_x, end_y], fill=rgb2, width=2)
                        
                        # Draw shorter rays between main rays for fuller starburst
                        mid_angle = angle + (math.pi / ray_count)
                        mid_end_x = center_x + (ray_length * 0.6) * math.cos(mid_angle)
                        mid_end_y = center_y + (ray_length * 0.6) * math.sin(mid_angle)
                        draw.line([center_x, center_y, mid_end_x, mid_end_y], fill=rgb2, width=1)
                    
                    # Draw center circle
                    circle_size = 4
                    draw.ellipse([
                        center_x - circle_size, center_y - circle_size,
                        center_x + circle_size, center_y + circle_size
                    ], fill=rgb2)
        elif pattern_type == 'sunburst':
            center_x = width // 2
            center_y = height // 2
            
            # Calculate optimal ray count based on image size
            # Larger images can support more rays while maintaining good proportions
            min_dimension = min(width, height)
            if min_dimension < 400:
                ray_count = 12
            elif min_dimension < 800:
                ray_count = 16
            else:
                ray_count = 20
            
            # Calculate ray length to extend beyond image edges
            max_distance = max(
                math.sqrt(center_x**2 + center_y**2),  # top-left corner
                math.sqrt((width - center_x)**2 + center_y**2),  # top-right corner
                math.sqrt(center_x**2 + (height - center_y)**2),  # bottom-left corner
                math.sqrt((width - center_x)**2 + (height - center_y)**2)  # bottom-right corner
            )
            ray_length = int(max_distance * 1.2)  # Extend well beyond edges
            
            # Draw alternating color wedges (not individual rays)
            angle_per_ray = (2 * math.pi) / ray_count
            
            for i in range(ray_count):
                start_angle = i * angle_per_ray
                end_angle = (i + 1) * angle_per_ray
                
                # Only fill every other wedge to create alternating pattern
                if i % 2 == 0:
                    # Create wedge points
                    points = [
                        (center_x, center_y),  # center point
                    ]
                    
                    # Add arc points for smooth wedge edge
                    arc_steps = 10  # More steps = smoother curve
                    for step in range(arc_steps + 1):
                        angle = start_angle + (end_angle - start_angle) * (step / arc_steps)
                        arc_x = center_x + ray_length * math.cos(angle)
                        arc_y = center_y + ray_length * math.sin(angle)
                        points.append((arc_x, arc_y))
                    
                    # Draw the wedge
                    draw.polygon(points, fill=rgb2)
            
            # Optional: Draw center circle (commented out for cleaner look)
            # center_size = min(width, height) // 20
            # draw.ellipse([
            #     center_x - center_size, center_y - center_size,
            #     center_x + center_size, center_y + center_size
            # ], fill=rgb2)
        
        # Paste image onto pattern background
        if img.mode == 'RGBA':
            background.paste(img, (0, 0), img)
            return background.convert('RGBA')
        else:
            background.paste(img, (0, 0))
            return background
    
    return img


def add_watermark(img, watermark_config):
    """Add watermark to image"""
    if watermark_config and watermark_config.get('type') == 'text':
        text = watermark_config.get('text', '').strip()
        if not text:  # Skip if no text provided
            return img
            
        position = watermark_config.get('position', 'bottom-right')
        size = watermark_config.get('size', 24)
        color = watermark_config.get('color', '#FFFFFF')
        opacity = watermark_config.get('opacity', 50)
        
        # Create watermark layer
        watermark_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        font = load_font(size)
        
        # Get text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate position
        margin = 20
        if position == 'top-left':
            x, y = margin, margin
        elif position == 'top-right':
            x, y = img.width - text_width - margin, margin
        elif position == 'bottom-left':
            x, y = margin, img.height - text_height - margin
        elif position == 'bottom-right':
            x, y = img.width - text_width - margin, img.height - text_height - margin
        elif position == 'center':
            x = (img.width - text_width) // 2
            y = (img.height - text_height) // 2
        else:
            x, y = margin, img.height - text_height - margin
        
        # Draw text with opacity
        color_with_alpha = color + format(int(255 * opacity / 100), '02X')
        draw.text((x, y), text, fill=color_with_alpha, font=font)
        
        # Composite watermark
        img = Image.alpha_composite(img, watermark_layer)
    
    return img