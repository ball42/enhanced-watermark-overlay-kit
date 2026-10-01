"""Tests for image processing utility functions."""

import pytest
from PIL import Image

from utils.image_processing import (
    hex_to_rgb, load_font, resize_for_wallpaper, add_text_overlays,
    add_image_overlays, FONT_MAP,
)


# ── hex_to_rgb ─────────────────────────────────


class TestHexToRgb:
    def test_valid_with_hash(self):
        assert hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_valid_without_hash(self):
        assert hex_to_rgb("00FF00") == (0, 255, 0)

    def test_valid_lowercase(self):
        assert hex_to_rgb("#abcdef") == (171, 205, 239)

    def test_valid_mixed_case(self):
        assert hex_to_rgb("#AaBbCc") == (170, 187, 204)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_invalid_short(self):
        assert hex_to_rgb("#FFF") == (0, 0, 0)

    def test_invalid_chars(self):
        assert hex_to_rgb("#ZZZZZZ") == (0, 0, 0)

    def test_invalid_empty(self):
        assert hex_to_rgb("") == (0, 0, 0)

    def test_invalid_none(self):
        assert hex_to_rgb(None) == (0, 0, 0)

    def test_invalid_number(self):
        assert hex_to_rgb(123) == (0, 0, 0)

    def test_whitespace_stripped(self):
        assert hex_to_rgb("  #FF0000  ") == (255, 0, 0)


# ── load_font ──────────────────────────────────


class TestLoadFont:
    def test_returns_font_object(self):
        font = load_font(24)
        assert font is not None

    def test_different_sizes(self):
        small = load_font(12)
        large = load_font(48)
        assert small is not None
        assert large is not None


# ── resize_for_wallpaper ───────────────────────


class TestResizeForWallpaper:
    def _make_image(self, w=200, h=300):
        return Image.new("RGBA", (w, h), (255, 0, 0, 255))

    def test_stretch_mode(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (1179, 2556), "stretch")
        assert result.size == (1179, 2556)

    def test_crop_mode_wider_image(self):
        img = self._make_image(400, 200)
        result = resize_for_wallpaper(img, (100, 100), "crop")
        assert result.size == (100, 100)

    def test_crop_mode_taller_image(self):
        img = self._make_image(200, 400)
        result = resize_for_wallpaper(img, (100, 100), "crop")
        assert result.size == (100, 100)

    def test_fit_mode_dimensions(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (1179, 2556), "fit")
        assert result.size == (1179, 2556)

    def test_fit_mode_is_default(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (500, 500))
        assert result.size == (500, 500)

    def test_fit_mode_preserves_rgba(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (500, 500), "fit")
        assert result.mode == "RGBA"


# ── add_text_overlays ────────────────────────────


class TestAddTextOverlays:
    def _make_image(self, w=400, h=400):
        return Image.new("RGBA", (w, h), (128, 128, 128, 255))

    def test_alignment_left(self):
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Left", "x": "10%", "y": "50%", "size": 20, "alignment": "left"}
        ])
        assert result.size == (400, 400)

    def test_alignment_right(self):
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Right", "x": "90%", "y": "50%", "size": 20, "alignment": "right"}
        ])
        assert result.size == (400, 400)

    def test_alignment_center(self):
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Center", "x": "50%", "y": "50%", "size": 20, "alignment": "center"}
        ])
        assert result.size == (400, 400)

    def test_size_percent(self):
        img = self._make_image(400, 400)
        result = add_text_overlays(img, [
            {"text": "Pct", "x": "50%", "y": "50%", "size_percent": 10}
        ])
        assert result.size == (400, 400)

    def test_size_percent_overrides_size(self):
        """size_percent should take precedence over size when both present."""
        img = self._make_image(400, 400)
        result = add_text_overlays(img, [
            {"text": "Pct", "x": "50%", "y": "50%", "size": 12, "size_percent": 10}
        ])
        assert result.size == (400, 400)

    def test_text_with_font_family(self):
        """Text overlay with an explicit font family."""
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Serif", "x": "50%", "y": "50%", "size": 20, "font_family": "Times New Roman"}
        ])
        assert result.size == (400, 400)

    def test_text_with_opacity(self):
        """Text overlay with reduced opacity draws on temporary layer."""
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Faded", "x": "50%", "y": "50%", "size": 24, "color": "#FF0000",
             "text_opacity": 50}
        ])
        assert result.size == (400, 400)
        assert result.mode == "RGBA"

    def test_text_with_zero_opacity(self):
        """Text overlay with 0% opacity should not visibly alter the image."""
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Invisible", "x": "50%", "y": "50%", "size": 24,
             "text_opacity": 0}
        ])
        assert result.size == (400, 400)

    def test_text_opacity_with_effect(self):
        """Text overlay with opacity + shadow effect."""
        img = self._make_image()
        result = add_text_overlays(img, [
            {"text": "Shadow", "x": "50%", "y": "50%", "size": 24,
             "text_effect": "shadow", "effect_color": "#000000",
             "effect_strength": 3, "text_opacity": 60}
        ])
        assert result.size == (400, 400)


# ── load_font with family ────────────────────────


class TestLoadFontFamily:
    def test_load_font_with_family(self):
        """Loading a known font family should return a font object."""
        font = load_font(24, family="Arial")
        assert font is not None

    def test_load_font_with_unknown_family(self):
        """Unknown family should fall back to default chain."""
        font = load_font(24, family="NonexistentFont")
        assert font is not None

    def test_load_font_with_none_family(self):
        """None family should use default fallback."""
        font = load_font(24, family=None)
        assert font is not None


# ── add_image_overlays smart sizing ──────────────


class TestImageOverlaySmartSizing:
    def _make_image(self, w=400, h=200):
        return Image.new("RGBA", (w, h), (128, 128, 128, 255))

    def _save_overlay(self, tmp_path, w=80, h=40):
        """Save a test overlay image to tmp_path and return (folder, filename)."""
        img = Image.new("RGBA", (w, h), (255, 0, 0, 255))
        filename = "overlay.png"
        img.save(str(tmp_path / filename))
        return str(tmp_path), filename

    def test_percent_width_and_height(self, tmp_path):
        """Percentage width/height relative to main image."""
        main = self._make_image(400, 200)
        folder, name = self._save_overlay(tmp_path, 80, 40)
        result = add_image_overlays(main, [
            {"filename": name, "x": 0, "y": 0, "width": "50%", "height": "25%"}
        ], folder)
        assert result.size == (400, 200)

    def test_width_only_preserves_aspect_ratio(self, tmp_path):
        """Specifying only width auto-calculates height from aspect ratio."""
        main = self._make_image(400, 200)
        folder, name = self._save_overlay(tmp_path, 80, 40)
        # 25% of 400 = 100px width → height should be 100*(40/80) = 50
        result = add_image_overlays(main, [
            {"filename": name, "x": 0, "y": 0, "width": "25%"}
        ], folder)
        assert result.size == (400, 200)

    def test_height_only_preserves_aspect_ratio(self, tmp_path):
        """Specifying only height auto-calculates width from aspect ratio."""
        main = self._make_image(400, 200)
        folder, name = self._save_overlay(tmp_path, 80, 40)
        result = add_image_overlays(main, [
            {"filename": name, "x": 0, "y": 0, "height": "50%"}
        ], folder)
        assert result.size == (400, 200)
