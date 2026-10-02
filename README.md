<div align="center">

# Enhanced Watermark Overlay Kit (EWOK)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

A web application for image editing with watermark and overlay capabilities.

</div>

---

## Features

- **Image Upload** — JPG, PNG, GIF, BMP, WebP (max 16MB) with drag-and-drop
- **Opacity & Saturation** — Adjust transparency and color intensity
- **Text Overlays** — Multiple overlays with position, size, color, and effects (shadow, outline, glow)
- **Click-to-Place** — Click the preview image to position text overlays
- **Watermarks** — Text watermarks with corner/center positioning and adjustable opacity
- **Wallpaper Mode** — Resize to device presets (iPhone, iPad, MacBook, iMac, etc.)
- **Fit Modes** — Fit, crop, or stretch to target dimensions
- **Backgrounds** — Solid color, gradient, or pattern (dots, stripes, checker, starburst, sunburst)
- **Live Preview** — See changes before downloading

## Wallpaper Presets

| Category | Presets |
|----------|---------|
| iPhone | 15 Pro, 15, 14 Pro, 14 |
| iPad | Pro 12.9", Air, Standard |
| MacBook | Air 13", Pro 14", Pro 16" |
| Desktop | iMac 24", Studio Display, Pro Display XDR |
| Standard | 1080p, 4K, 4:3, Square |

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repository-url>
cd enhanced-watermark-overlay-kit
uv sync
uv run ewok
```

Open `http://127.0.0.1:5055` in your browser. EWOK listens on localhost only and has no login, so don't expose it to a network. `--port` (or `EWOK_PORT`) changes the port, and `EWOK_DEBUG=1` turns on Flask's debug mode.

## Testing

```bash
uv run pytest
(cd wallrender && uv run --with pytest pytest)
```

The app tests cover upload, processing, download, preview, path traversal protection, color validation, font loading, wallpaper resize modes and the local-only server settings. `wallrender/` has its own suite.

## Architecture

```
app.py                  # Entry point
app_factory.py          # Flask factory with blueprint registration and cleanup
config.py               # Settings, wallpaper presets, SECRET_KEY
views/
  api.py                # REST endpoints: upload, process, download, preview
  main.py               # Page route
utils/
  image_processing.py   # PIL operations: resize, overlays, backgrounds, watermarks
  cleanup.py            # Periodic temp file cleanup (1hr max age, 5min interval)
templates/
  index.html            # Jinja2 template (semantic HTML, links external CSS/JS)
static/
  css/style.css         # Design system (CSS custom properties, responsive)
  js/app.js             # Client app (IIFE, addEventListener, click-to-place)
  ewok.png              # Logo
tests/
  conftest.py           # Fixtures: isolated app, test client, sample image helper
  test_api.py           # Endpoint tests
  test_utils.py         # Unit tests for image processing helpers
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload an image file |
| `POST` | `/api/process` | Process image with parameters |
| `GET` | `/api/preview/<filename>` | Preview processed image |
| `GET` | `/api/original/<filename>` | Preview original upload |
| `GET` | `/api/download/<filename>` | Download processed image |

## Configuration

| Setting | Default |
|---------|---------|
| Upload folder | `static/uploads/` |
| Temp folder | `temp/` |
| Max file size | 16 MB |
| Formats | PNG, JPG, JPEG, GIF, BMP, WebP |
| SECRET_KEY | `$SECRET_KEY` env var (random fallback with warning) |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0, Python 3.8+ |
| Image Processing | Pillow (PIL) |
| Frontend | HTML5, CSS3, vanilla JavaScript |
| Icons | Font Awesome 6 |
| Testing | pytest, pytest-flask |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/name`)
3. Run tests (`pytest tests/ -v`)
4. Commit and push
5. Open a Pull Request

## License

MIT — see [LICENSE](LICENSE).
