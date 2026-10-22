<div align="center">

# Enhanced Watermark Overlay Kit (EWOK)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

A local template designer for Brander device wallpapers, with a photo editor for watermarks and overlays.

</div>

---

EWOK runs on your own computer. Its main page is the **template designer** (`/template`): you design a wallpaper template for JAWA's Brander, which fills in each device's details (name, serial number, asset tag and more) when it sets the wallpaper. The **photo editor** (`/`) is EWOK's original tool: it adds text, watermarks, overlays and backgrounds to one photo.

Both modes preview through `wallrender/`, or Pillow for the photo editor. `wallrender` is the renderer that JAWA vendors, so the template preview is what a device receives.

## Template designer (`/template`)

- **Canvas and background** — iPhone and iPad presets or a custom size, and a color or an image background.
- **Layers** — text, QR code, image and panel (a translucent backdrop) layers. Text and QR data use device variables: `{{device_name}}`, `{{serial_number}}`, `{{asset_tag}}`, `{{jss_id}}`, `{{location.building}}`, `{{role.*}}`, and `{{user.*}}` when the template opts in to personal fields.
- **Live preview** — renders through `wallrender` against sample devices after each change, with warnings for missing values, missing glyphs, overflow and low contrast.
- **Stress view** — extra renders with every value long, then empty, then once per role.
- **Your devices** — load a CSV of real devices (a Jamf Pro inventory export with value names in the header row) and see a thumbnail of each, with the devices that have warnings first; pick one to preview it.
- **Placement** — drag boxes on the preview, or move and resize them with the arrow keys.
- **Devices** — safe-area guides for the clock, controls and dock, and a grid that shows how each iPhone and iPad crops the canvas. The checked devices follow the canvas preset until you change them.
- **Role variants** — one template with a background and wording per device role, read from a Jamf extension attribute.
- **Asset library** — PNG and JPEG images that backgrounds and image layers use.
- **Export** — a `.brander.json` package for JAWA's template store, or a `.zip` bundle for Brander's assets folder. Both open again in EWOK.
- **Renderer version** — a package records the wallrender it was made with (`wallrender`) and the lowest release that renders every feature it uses (`requires_wallrender`). The preview warns when a feature is newer than the release JAWA runs.
- **Draft** — the template is kept in the browser, so a reload does not lose it.

## Photo editor (`/`)

- **Image upload** — JPG, PNG, GIF, BMP or WebP (16 MB at most), with drag and drop.
- **Adjustments** — opacity, saturation, brightness, contrast, blur or sharpen, rotation and resize.
- **Text overlays** — several overlays with position, size, color and effects (shadow, outline, glow). Click the preview to place one.
- **Image overlays and watermarks** — corner or center positions, with adjustable opacity.
- **Wallpaper mode** — resize to device presets (iPhone, iPad, MacBook, iMac and more) by fit, crop or stretch.
- **Backgrounds** — solid color, gradient or pattern (dots, stripes, checker, starburst, sunburst).
- **Live preview** — the preview renders again a moment after each change. **Update preview** renders at once.

Uploads expire one hour after their last use.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ball42/enhanced-watermark-overlay-kit.git
cd enhanced-watermark-overlay-kit
uv sync
uv run ewok
```

Open `http://127.0.0.1:5055/template` in your browser. EWOK listens on localhost only and has no login, so don't expose it to a network. `--port` (or `EWOK_PORT`) changes the port, and `EWOK_DEBUG=1` turns on Flask's debug mode.

### JAWA's wallrender version

JAWA vendors its own copy of `wallrender`. An older copy renders a feature it does not know as if it were absent: text with a `weight` of Medium, Semibold or Bold shows as Regular on devices. **JAWA must vendor wallrender 0.12.0 or later before you use `weight`.**

`EWOK_WALLRENDER_TARGET` is the release JAWA runs (default `0.9.0`). The preview warns for each feature that needs a newer release. Set it to the release JAWA vendors, for example `EWOK_WALLRENDER_TARGET=0.13.0 uv run ewok`.

## Testing

```bash
uv run pytest
(cd wallrender && uv run --project .. pytest)
```

The app tests cover both modes: the photo API (upload, processing, download, preview, expiry, path traversal), the template API (preview, asset library, export and import), the pages, and the local-only server settings. Browser tests in `tests/browser` drive both pages in headless Chromium. They are skipped until Playwright is installed:

```bash
uv sync --group browser
uv run playwright install chromium
uv run pytest tests/browser
```

`wallrender/` has its own suite, and its own README for the template format and the `wallrender` command line.

## Architecture

```
app.py                  # Entry point: the `ewok` command
app_factory.py          # Flask factory: config, blueprints, local-only checks, cleanup
config.py               # Settings, canvas presets, sample devices, Brander variables
views/
  main.py               # Pages: / and /template
  api.py                # Photo editor API: upload, process, download, preview
  template_api.py       # Template designer API: preview, asset library, export, import
utils/
  image_processing.py   # Photo editor: resize, overlays, backgrounds, watermarks (Pillow)
  cleanup.py            # Removes uploads and results an hour after their last use
templates/
  index.html            # Photo editor page
  template.html         # Template designer page
static/
  css/style.css         # Design tokens shared with JAWA, Endor theme
  css/template.css      # Template designer layout
  js/app.js             # Photo editor
  js/template.js        # Template designer
wallrender/             # Renderer shared with JAWA (Pillow + qrcode only)
  wallrender/schema.py      # Validates untrusted templates
  wallrender/render.py      # Rendering and lint warnings
  wallrender/devices.py     # Device profiles, crops and covered areas
  wallrender/roles.py       # Role variants
  wallrender/variables.py   # {{variable}} substitution
  wallrender/cli.py         # `wallrender preview` and `wallrender devices`
tests/                  # App tests; tests/browser for Playwright
```

## API endpoints

Photo editor:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload an image file |
| `POST` | `/api/process` | Process the image with the given settings |
| `GET` | `/api/preview/<filename>` | Preview a processed image |
| `GET` | `/api/original/<filename>` | Preview the original upload |
| `GET` | `/api/download/<filename>` | Download a processed image |

Template designer:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/template/preview` | Render a template with sample values; returns images and warnings, with device warnings for the chosen devices and screen |
| `POST` | `/api/template/preview-batch` | Render a template for up to 200 devices (rows of a CSV loaded in the browser); returns a 240 px thumbnail and the warnings for each, and keeps nothing |
| `GET` | `/api/template/assets` | List the asset library |
| `POST` | `/api/template/assets` | Add a PNG or JPEG to the asset library |
| `GET` | `/api/template/assets/<asset_id>` | Serve one asset |
| `DELETE` | `/api/template/assets/<asset_id>` | Delete one asset |
| `POST` | `/api/template/export` | Download a `.zip` bundle: the template JSON, its assets and a README |
| `POST` | `/api/template/package` | Download a `.brander.json` package for JAWA's template store |
| `POST` | `/api/template/import` | Open a template `.json`, a `.zip` bundle or a `.brander.json` package |

## Configuration

| Setting | Default |
|---------|---------|
| Address | `127.0.0.1:5055` (`--port` or `EWOK_PORT`) |
| Upload folder | `static/uploads/` |
| Temp folder | `temp/` |
| Template asset library | `template_assets/` |
| Max file size | 16 MB |
| Photo formats | PNG, JPG, JPEG, GIF, BMP, WebP |
| SECRET_KEY | `$SECRET_KEY` env var (random fallback) |

## Technology stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.1, Python 3.12+ |
| Rendering | Pillow 11.3 (pinned below 12, the same as JAWA), qrcode |
| Frontend | HTML, CSS, vanilla JavaScript |
| Icons | Font Awesome 6 |
| Testing | pytest, pytest-flask, Playwright |

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/name`).
3. Run both test suites (see Testing).
4. Commit and push.
5. Open a pull request.

## License

MIT — see [LICENSE](LICENSE).
