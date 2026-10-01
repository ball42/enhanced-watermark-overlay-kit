# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Enhanced Watermark Overlay Kit (EWOK) — a Flask web application for image editing with watermark and overlay capabilities. Users can upload images, adjust opacity/saturation, add text overlays (with click-to-place positioning), apply watermarks, add backgrounds, and create wallpapers with device presets.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
python app.py
# App available at http://localhost:5000

# Run tests
pytest tests/ -v
```

## Architecture

The app uses the Flask factory pattern with blueprints:

```
app.py                  # Entry point — calls create_app()
app_factory.py          # Factory: config, blueprints, cleanup hook
config.py               # Settings, wallpaper presets, SECRET_KEY
views/
  api.py                # REST API: upload, process, download, preview (with path traversal protection)
  main.py               # Serves index page
utils/
  image_processing.py   # PIL: resize, text overlays, image overlays, backgrounds, watermarks
  cleanup.py            # Periodic cleanup of temp/upload files (before_request hook)
templates/
  index.html            # Jinja2 template — semantic HTML, links to external CSS/JS
static/
  css/style.css         # Design system with CSS custom properties
  js/app.js             # Client-side app (IIFE, no inline handlers, click-to-place)
  ewok.png              # Logo
tests/
  conftest.py           # Fixtures: isolated app with tmp_path dirs, test client, image helper
  test_api.py           # Upload, process, download, preview, path traversal tests
  test_utils.py         # hex_to_rgb, load_font, resize_for_wallpaper tests
```

### Key Patterns

- **Path safety:** All file-serving endpoints use `safe_filepath()` in `views/api.py` — `os.path.basename()` + `os.path.realpath()` containment check
- **Hex colors:** Validated via `hex_to_rgb()` in `utils/image_processing.py` — regex-based, returns `(0,0,0)` fallback
- **Font loading:** `load_font(size)` helper with system font fallback chain
- **Temp cleanup:** `utils/cleanup.py` runs via `before_request` hook — removes files older than 1 hour, at most every 5 minutes
- **SECRET_KEY:** Uses `$SECRET_KEY` env var; falls back to `secrets.token_hex(32)` with a warning log

## Repository Guidelines

- Uses MIT License
- Default branch: main
- Tests: `pytest tests/ -v` (35 tests, all should pass)
