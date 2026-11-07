# EWOK architecture

This document explains how EWOK is put together. For installation, features and the API list, see the [README](../README.md).

## Overview

EWOK is a single Flask process that runs on one person's computer. It has two pages and no database, no login and no external service.

```
 Browser (localhost only)
   |
   |  /            photo editor      static/js/app.js
   |  /template    template designer static/js/template.js
   v
 Flask app (app_factory.create_app)
   |-- views/main.py          renders the two pages
   |-- views/api.py           photo API        --> utils/image_processing.py (Pillow)
   |-- views/template_api.py  template API     --> wallrender/ (Pillow + qrcode)
   |-- before_request: local_only, run_cleanup (utils/cleanup.py)
   v
 Folders on disk (all gitignored)
   static/uploads/   photo uploads and results
   temp/             processed photos
   template_assets/  the template designer's asset library
```

## The two modes

**Template designer (`/template`)** is the main tool. A template is a JSON document: a canvas, a background, and an ordered list of layers (text, QR code, image, panel) that contain `{{variables}}` such as `{{device_name}}`. The browser holds the template and sends it to `/api/template/preview`. The server validates it, renders it with `wallrender` against sample devices, and returns PNG data URLs plus lint warnings. Nothing about the template is stored on the server, except images added to the asset library. The browser keeps a draft so a reload does not lose work.

**Photo editor (`/`)** is the original tool. The browser uploads one image to `/api/upload`; `/api/process` applies the requested adjustments, overlays, background and resize with Pillow and writes a result file; `/api/preview/...` and `/api/download/...` serve it back.

## wallrender

`wallrender/` is a separate Python project in the same repository, with its own `pyproject.toml`, tests and README. It turns a template plus a dictionary of device values into an image. It depends only on Pillow and qrcode and knows nothing about Flask.

| Module | Role |
|---|---|
| `schema.py` | Validates untrusted templates: size caps, role rules, personal-field opt-in, QR rules, screen choice. |
| `render.py` | Draws the layers, and produces lint warnings (missing values, missing glyphs, overflow, contrast). |
| `devices.py`, `device_profiles.json` | Device profiles: how each phone or tablet crops the canvas and which areas the clock, controls and dock cover. |
| `roles.py` | Role variants: a different background and wording per device role. |
| `variables.py` | `{{variable}}` substitution, including dotted names. |
| `cli.py` | The `wallrender preview` and `wallrender devices` commands. |

The same code is vendored into JAWA's Brander feature. This is deliberate: because the preview and the device wallpaper run the same renderer on the same Pillow version, the preview is what a device receives.

## Export and import

- `/api/template/package` produces a single `.brander.json` file for JAWA's template store. It records the wallrender version used (`wallrender`) and the lowest release that renders every feature the template uses (`requires_wallrender`).
- `/api/template/export` produces a `.zip` bundle: the template JSON, its assets, and a README, for Brander's assets folder.
- `/api/template/import` accepts a plain template JSON, a `.zip` bundle or a `.brander.json` package. Imported assets go into the asset library.

## Safety model

EWOK has no authentication, so it limits who can reach it:

- It binds to `127.0.0.1`. A `before_request` hook (`local_only`) refuses any request whose Host header is not `127.0.0.1`, `localhost` or `[::1]` (DNS rebinding), and refuses write requests whose `Sec-Fetch-Site` header says they came from another site.
- File-serving routes use `safe_filepath()` in `views/api.py`: `os.path.basename()` plus a `realpath` containment check.
- Every `Image.open()` passes an explicit `formats=` list, so a file with a misleading extension is refused rather than decoded by an unexpected plugin. Keep this on any new `Image.open()` call.
- Uploads and results are deleted an hour after last use. `utils/cleanup.py` runs from a `before_request` hook at most every five minutes.

## Design decisions

- **Same renderer as the consumer.** Sharing wallrender with JAWA removes a class of "it looked different on the device" bugs. The cost is that the Pillow version must match; both projects pin `Pillow>=11.3,<12` and move together.
- **No server-side template storage.** The browser owns the template, so there is nothing to migrate or clean up and nothing sensitive on disk.
- **Validate at the boundary.** Templates and packages are untrusted input, so `schema.py` checks them before any rendering.
- **Vanilla JavaScript, no build step.** The frontend is plain files under `static/`; there is nothing to compile.
- **Shared design tokens.** `static/css/vendor/` holds generated design-token files copied in from the shared design system. Replace them with newer generated copies; do not edit them by hand.
