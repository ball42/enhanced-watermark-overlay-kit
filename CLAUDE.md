# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Enhanced Watermark Overlay Kit (EWOK) is a local Flask tool. Its main purpose is the **template designer** (`/template`): it designs wallpaper templates for JAWA's Brander, with text, QR, image and panel layers that use device variables (`{{device_name}}`, `{{serial_number}}`, `{{asset_tag}}`, `{{jss_id}}`, `{{location.building}}`, `{{role.*}}`, opt-in `{{user.*}}`). It previews live through `wallrender/` against sample devices, shows device crops and covered areas, supports role variants, and exports a `.brander.json` package or a `.zip` bundle. The **photo editor** (`/`) is the original tool: upload one image, adjust it, add text overlays (click to place), watermarks, image overlays and backgrounds, and resize it to wallpaper presets.

## Development Commands

```bash
# Install (Python 3.12+, uv); wallrender/ is installed editable alongside
uv sync

# Run: serves on http://127.0.0.1:5055 only (EWOK has no auth)
uv run ewok
# EWOK_DEBUG=1 turns on Flask debug; --port or EWOK_PORT changes the port

# Run tests
uv run pytest
(cd wallrender && uv run --project .. pytest)

# Browser tests (tests/browser, headless Chromium; skipped without Playwright)
uv sync --group browser
uv run playwright install chromium
uv run pytest tests/browser
```

## Architecture

The app uses the Flask factory pattern with blueprints:

```
app.py                  # Entry point: the `ewok` command, calls create_app()
app_factory.py          # Factory: config, blueprints, local-only checks, cleanup hook
config.py               # Settings, canvas presets and their devices, sample devices, Brander variables
views/
  main.py               # Pages: / (photo editor) and /template (template designer)
  api.py                # Photo API: upload, process, download, preview (path traversal protection)
  template_api.py       # Template API: preview (wallrender), asset library, .zip and .brander.json export, import
utils/
  image_processing.py   # Photo editor: resize, text overlays, image overlays, backgrounds, watermarks
  cleanup.py            # Removes uploads and results an hour after last use (before_request hook)
templates/
  index.html            # Photo editor page
  template.html         # Template designer page
static/
  css/style.css         # Design tokens shared with JAWA, Endor theme
  css/template.css      # Template designer layout
  js/app.js             # Photo editor (IIFE, no inline handlers, live preview, click-to-place)
  js/template.js        # Template designer (layers, drag placement, devices, roles, draft)
wallrender/             # Renderer shared with JAWA (vendored, hash-pinned there); own pyproject and tests
  wallrender/schema.py      # Validation of untrusted templates (caps, roles, person_fields, QR rule, screen)
  wallrender/render.py      # Rendering and lint (missing values, glyphs, overflow, WCAG contrast)
  wallrender/devices.py     # device_profiles.json, crop and safe-area fit
  wallrender/roles.py, variables.py
  wallrender/cli.py         # `wallrender preview TEMPLATE VALUES -o OUT [--stress --devices IDS --strict]`, `wallrender devices`
tests/
  conftest.py           # Fixtures: isolated app with tmp_path dirs, test client, image helper
  test_*.py             # Photo API, template API, pages, foundation, isolation
  browser/              # Playwright tests of both pages (skipped without Playwright)
```

Data lives only in gitignored folders (`static/uploads/`, `temp/`, `template_assets/`). There is no database or external service. Views read the upload and temp folders from `current_app.config`, never from module-level copies.

### Key Patterns

- **Design: one family with JAWA.** `static/css/style.css` uses JAWA's tokens (Inter and JetBrains Mono, parchment surfaces, borders, radii, shadows, primary blue `#3c6aa7`). EWOK's own identity is Endor: the forest navbar (`#2f4a33`) with a treeline edge, a bark accent and moss success color. Change shared tokens in both repos. Status is never color alone: messages and toasts lead with a word, switches say On or Off.
- **Pillow pin:** `Pillow>=11.3,<12`, the same as JAWA. Text pixels differ between Pillow releases, so the preview only matches devices on the same version; change both repos together.
- **Path safety:** All file-serving endpoints use `safe_filepath()` in `views/api.py` — `os.path.basename()` + `os.path.realpath()` containment check
- **Hex colors:** Validated via `hex_to_rgb()` in `utils/image_processing.py` — regex-based, returns `(0,0,0)` fallback
- **Font loading:** `load_font(size)` helper with system font fallback chain
- **Temp cleanup:** `utils/cleanup.py` runs via `before_request` hook — removes files older than 1 hour, at most every 5 minutes
- **SECRET_KEY:** Uses `$SECRET_KEY` env var; falls back to `secrets.token_hex(32)` with a warning log

## Repository Guidelines

- Uses MIT License
- Default branch: main
- Tests: `uv run pytest` and `(cd wallrender && uv run --project .. pytest)`; all should pass
