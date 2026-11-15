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
- **Live preview** — renders through `wallrender` against sample devices after each change, with warnings for missing values, missing glyphs, overflow and low contrast. **Save as a sample device** names the values you typed and adds them to Preview with, kept in this browser only and never in a download; saved devices can be renamed and removed. A low-contrast warning on a text layer carries its fix: **Use white text** (or dark, whichever passes) or **Add a backdrop**, a panel just behind the text at the lowest opacity that reaches WCAG's ratio. Either says the ratio before and after ("✓ Contrast 1.5:1 → 5.0:1") with Undo.
- **Stress view** — extra renders with every value long, then empty, then once per role.
- **Your devices** — load a CSV of real devices (a Jamf Pro inventory export with value names in the header row) and see a summary (how many fit, the problems by kind and by layer) above a thumbnail of each, with the devices that have warnings first; pick one to preview it. Long lists are checked ten at a time with a progress meter and a Stop button. Check again compares the numbers with the last check (▼ fewer, ▲ more). A switch, Off by default, remembers the list in this browser. When names shrink, **Fit the longest name** sets the name layer's size so every name prints at full size, says what changed ("Layer 1 size 0.028 → 0.022") with Undo, and checks again.
- **Placement** — drag boxes on the preview, or move and resize them with the arrow keys. While dragging, a box snaps to the canvas center lines, the guide device's safe areas and the edges and middles of other layers, with a labelled guide ("aligns with Layer 1"); hold Option (Alt) to drag freely.
- **Devices** — safe-area guides for the clock, controls and dock, and a grid that shows how each iPhone and iPad crops the canvas. The checked devices follow the canvas preset until you change them.
- **Role variants** — one template with a background and wording per device role, read from a Jamf extension attribute.
- **Asset library** — PNG and JPEG images that backgrounds and image layers use.
- **Ready for JAWA?** — hovering Download for JAWA, or its ▾ button, shows a preflight: whether JAWA's wallrender renders it, how many of your devices fit, the sample render's warnings by kind, and whether the assets are there, each with the way to it. When all pass, the button reads "Ready: Download for JAWA".
- **Export** — a `.brander.json` package for JAWA's template store, or a `.zip` bundle for Brander's assets folder. Both open again in EWOK. After a package download the top bar says its sha256, the one JAWA's store shows for the upload, and More › Downloads lists the last 20 with a thumbnail.
- **Renderer version** — a package records the wallrender it was made with (`wallrender`) and the lowest release that renders every feature it uses (`requires_wallrender`). The preview warns when a feature is newer than the release JAWA runs.
- **Draft** — the template is kept in the browser, so a reload does not lose it.

## Photo editor (`/`)

- **Image upload** — JPG, PNG, GIF, BMP or WebP (16 MB at most), with drag and drop.
- **Adjustments** — opacity, saturation, brightness, contrast, blur or sharpen, rotation and resize.
- **Text overlays** — several overlays with position, size, color and effects (shadow, outline, glow). Click the preview to place one.
- **Image overlays and watermarks** — corner or center positions, with adjustable opacity.
- **Wallpaper mode** — resize by fit, crop or stretch to the template designer's canvases (listed first, so background art is not upscaled or cropped there), the iPhones and iPads wallrender checks, or Mac and display sizes.
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

Open `http://127.0.0.1:5055/template` in your browser, or start with `ewok --open` to open it for you. EWOK listens on localhost only and has no login, so don't expose it to a network. `--port` (or `EWOK_PORT`) changes the port, and `EWOK_DEBUG=1` turns on Flask's debug mode.

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
| `POST` | `/api/template/fit-names` | The size each named text layer needs so the devices sent (up to 200) print without shrinking; changes nothing, and says when that size would be too small to read |
| `POST` | `/api/template/preview-batch` | Render a template for up to 200 devices (rows of a CSV loaded in the browser); returns a 240 px thumbnail and the warnings for each, and keeps nothing; optional `first` numbers unnamed devices when the page sends a long list in chunks |
| `GET` | `/api/template/assets` | List the asset library |
| `POST` | `/api/template/assets` | Add a PNG or JPEG to the asset library |
| `GET` | `/api/template/assets/<asset_id>` | Serve one asset |
| `DELETE` | `/api/template/assets/<asset_id>` | Delete one asset (it waits a day in `template_assets/.trash/`) |
| `POST` | `/api/template/assets/<asset_id>/restore` | Undo a delete: bring the asset back from the trash |
| `POST` | `/api/template/export` | Download a `.zip` bundle: the template JSON, its assets and a README |
| `POST` | `/api/template/backdrop` | For a low-contrast text layer: the panel to put just behind it, at the lowest opacity a real render confirms reaches WCAG's ratio; changes nothing |
| `POST` | `/api/template/package` | Download a `.brander.json` package for JAWA's template store; the `X-Template-SHA256` header is the sha256 JAWA's store shows for it (of the template dumped with indent 2 and a newline) |
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
| Icons | Font Awesome Free 6 (solid), vendored in `static/vendor/fontawesome/`, so no page loads anything from the internet |
| Testing | pytest, pytest-flask, Playwright |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `uv: command not found` | Install [uv](https://docs.astral.sh/uv/), then run `uv sync` again. |
| Port 5055 is in use | Start on another port: `uv run ewok --port 5056`. |
| 403 from another computer or a hostname | EWOK answers only to `127.0.0.1`, `localhost` and `[::1]`. Open it by one of those. |
| Weight (Medium, Semibold, Bold) looks like Regular on devices | The JAWA install vendors a wallrender older than 0.12.0. Update JAWA's copy. |
| Preview text differs slightly from the device | Pillow versions differ between EWOK and JAWA. Both pin `Pillow>=11.3,<12`; keep them equal. |
| Uploaded photo disappears | Uploads are deleted an hour after last use. Upload it again. |

## Maintenance

- **Dependencies.** Pillow is pinned below 12 to match JAWA, and a Pillow change shifts text pixels. Move EWOK and JAWA to a new Pillow release together. Run `uv lock --upgrade` to refresh other dependencies, then both test suites.
- **Design files.** `static/css/vendor/` and `static/js/vendor/` are generated copies of the shared design system. Replace them whole; do not edit them.
- **wallrender.** It is versioned in `wallrender/pyproject.toml`. When you release a new version, update the copy vendored in JAWA and raise `EWOK_WALLRENDER_TARGET`'s default if appropriate.
- **Data.** Everything EWOK writes is under `static/uploads/`, `temp/` and `template_assets/`. Back up `template_assets/` if you rely on the asset library; the other two are disposable.
- **More detail.** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains the components and design decisions.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/name`).
3. Run both test suites (see Testing).
4. Commit and push.
5. Open a pull request.

## License

MIT — see [LICENSE](LICENSE).
