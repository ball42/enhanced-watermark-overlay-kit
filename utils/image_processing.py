"""
Image processing utilities for EWOK
Handles all image manipulation operations including resizing, overlays, backgrounds, and watermarks
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance


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


def add_text_overlays(img, text_overlays):
    """Add text overlays to image with center-aligned positioning and effects"""
    draw = ImageDraw.Draw(img)
    
    for overlay in text_overlays:
        text = overlay.get('text', '')
        if not text:
            continue
            
        x = overlay.get('x', 0)
        y = overlay.get('y', 0)
        size = overlay.get('size', 24)
        color = overlay.get('color', '#FFFFFF')
        text_effect = overlay.get('text_effect', 'none')
        effect_color = overlay.get('effect_color', '#000000')
        effect_strength = overlay.get('effect_strength', 3)
        
        try:
            # Try to use a system font
            font = ImageFont.truetype("Arial.ttf", size)
        except:
            try:
                # Fallback fonts
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", size)
            except:
                font = ImageFont.load_default()
        
        # Calculate text dimensions for center alignment
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Convert percentage positions to pixels or handle plain numbers
        if isinstance(x, str):
            if x.endswith('%'):
                x = int(float(x[:-1]) / 100 * img.width)
            else:
                try:
                    x = int(float(x))
                except ValueError:
                    x = img.width // 2  # fallback to center
        elif not isinstance(x, (int, float)):
            x = img.width // 2  # fallback to center
            
        if isinstance(y, str):
            if y.endswith('%'):
                y = int(float(y[:-1]) / 100 * img.height)
            else:
                try:
                    y = int(float(y))
                except ValueError:
                    y = img.height // 2  # fallback to center
        elif not isinstance(y, (int, float)):
            y = img.height // 2  # fallback to center
        
        # Adjust position to center the text at the specified coordinates
        centered_x = x - (text_width // 2)
        centered_y = y - (text_height // 2)
        
        # Ensure text doesn't go off the edges of the image
        centered_x = max(0, min(centered_x, img.width - text_width))
        centered_y = max(0, min(centered_y, img.height - text_height))
        
        # Apply text effects
        if text_effect == 'shadow':
            # Drop shadow effect
            shadow_offset = effect_strength
            draw.text((centered_x + shadow_offset, centered_y + shadow_offset), text, fill=effect_color, font=font)
        elif text_effect == 'outline':
            # Outline/stroke effect
            stroke_width = effect_strength
            # Draw text multiple times with slight offsets to create outline
            for adj in range(-stroke_width, stroke_width + 1):
                for adj2 in range(-stroke_width, stroke_width + 1):
                    if adj != 0 or adj2 != 0:  # Don't draw at center position yet
                        draw.text((centered_x + adj, centered_y + adj2), text, fill=effect_color, font=font)
        elif text_effect == 'glow':
            # Glow effect - multiple layers with decreasing opacity
            glow_radius = effect_strength * 2
            for radius in range(glow_radius, 0, -1):
                # Calculate alpha based on distance from center
                alpha = int(255 * (1 - radius / glow_radius) * 0.3)  # Max 30% opacity
                glow_color_with_alpha = effect_color + format(alpha, '02X')
                
                # Draw glow layer
                for angle in range(0, 360, 30):  # 12 points around circle
                    import math
                    glow_x = centered_x + radius * math.cos(math.radians(angle))
                    glow_y = centered_y + radius * math.sin(math.radians(angle))
                    draw.text((glow_x, glow_y), text, fill=glow_color_with_alpha, font=font)
        
        # Draw main text on top
        draw.text((centered_x, centered_y), text, fill=color, font=font)
    
    return img


def add_image_overlays(img, image_overlays, upload_folder):
    """Add image overlays to main image"""
    for overlay in image_overlays:
        overlay_path = os.path.join(upload_folder, overlay.get('filename', ''))
        if not os.path.exists(overlay_path):
            continue
            
        try:
            with Image.open(overlay_path) as overlay_img:
                if overlay_img.mode != 'RGBA':
                    overlay_img = overlay_img.convert('RGBA')
                
                # Resize overlay if specified
                if 'width' in overlay or 'height' in overlay:
                    width = overlay.get('width', overlay_img.width)
                    height = overlay.get('height', overlay_img.height)
                    overlay_img = overlay_img.resize((width, height), Image.Resampling.LANCZOS)
                
                # Apply opacity
                if 'opacity' in overlay and overlay['opacity'] != 100:
                    alpha = overlay_img.split()[-1]
                    alpha = alpha.point(lambda p: p * (overlay['opacity'] / 100.0))
                    overlay_img.putalpha(alpha)
                
                x = overlay.get('x', 0)
                y = overlay.get('y', 0)
                
                # Convert percentage positions to pixels
                if isinstance(x, str) and x.endswith('%'):
                    x = int(float(x[:-1]) / 100 * img.width)
                if isinstance(y, str) and y.endswith('%'):
                    y = int(float(y[:-1]) / 100 * img.height)
                
                img.paste(overlay_img, (x, y), overlay_img)
                
        except Exception as e:
            print(f"Error adding overlay: {e}")
            continue
    
    return img


def add_background(img, background_config):
    """Add background to image"""
    bg_type = background_config.get('type', 'color')
    
    if bg_type == 'color':
        color = background_config.get('color', '#FFFFFF')
        # Convert hex to RGB
        if color.startswith('#'):
            color = color[1:]
        rgb_color = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        
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
        # Create a gradient background
        start_color = background_config.get('start_color', '#FFFFFF')
        end_color = background_config.get('end_color', '#000000')
        direction = background_config.get('direction', 'vertical')  # vertical, horizontal, diagonal
        
        # Convert hex to RGB
        def hex_to_rgb(hex_color):
            if hex_color.startswith('#'):
                hex_color = hex_color[1:]
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        start_rgb = hex_to_rgb(start_color)
        end_rgb = hex_to_rgb(end_color)
        
        # Create gradient
        width, height = img.size
        background = Image.new('RGB', (width, height))
        
        if direction == 'horizontal':
            for x in range(width):
                ratio = x / width
                r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
                g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
                b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
                for y in range(height):
                    background.putpixel((x, y), (r, g, b))
        elif direction == 'diagonal':
            for x in range(width):
                for y in range(height):
                    ratio = (x + y) / (width + height)
                    r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
                    g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
                    b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
                    background.putpixel((x, y), (r, g, b))
        else:  # vertical
            for y in range(height):
                ratio = y / height
                r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
                g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
                b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
                for x in range(width):
                    background.putpixel((x, y), (r, g, b))
        
        # Paste image onto gradient background
        if img.mode == 'RGBA':
            background.paste(img, (0, 0), img)
            return background.convert('RGBA')
        else:
            background.paste(img, (0, 0))
            return background
            
    elif bg_type == 'pattern':
        # Create pattern background
        pattern_type = background_config.get('pattern', 'dots')
        color1 = background_config.get('color1', '#FFFFFF')
        color2 = background_config.get('color2', '#E0E0E0')
        
        # Convert hex to RGB
        def hex_to_rgb(hex_color):
            if hex_color.startswith('#'):
                hex_color = hex_color[1:]
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
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
            # Starburst pattern
            import math
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
            # Central sunburst pattern (like Japanese Rising Sun flag)
            import math
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
        
        try:
            font = ImageFont.truetype("Arial.ttf", size)
        except:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", size)
            except:
                font = ImageFont.load_default()
        
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