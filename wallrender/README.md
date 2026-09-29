# wallrender

Renders wallpaper **templates** with **device variables**. EWOK uses it to preview a design; JAWA's Brander uses the same code (vendored, hash-pinned) to render each device's wallpaper. The preview is therefore exactly what a device receives.

It depends only on Pillow and qrcode: no Flask, no network, no Jamf.

```python
from wallrender import render, lint, validate

problems = validate(template)                     # [] when the template is renderable
image = render(template, values, asset_resolver)  # RGB PIL image, ready to deliver
warnings = lint(template, values, asset_resolver) # missing values, missing glyphs
```

- `values` is a dict of device data, for example built from the verified Jamf record. Nested dicts are addressed with dots: `{{location.building}}`.
- `asset_resolver(asset_id)` returns PNG or JPEG bytes, or a PIL image; raise `KeyError` for an unknown id. Templates never contain file paths, only asset ids.
- Every failure, whether from the template, the values or the assets, raises `TemplateError`, never another exception.

## Template format (schema v1)

```json
{
  "schema_version": 1,
  "name": "Brander basic",
  "canvas": {"width": 1290, "height": 2796},
  "background": {"color": "#0B2545"},
  "layers": [
    {"type": "text", "text": "{{device_name}}", "box": {"x": 0.08, "y": 0.6, "w": 0.84, "h": 0.05},
     "size": 0.028, "color": "#FFFFFF", "align": "center"},
    {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.35, "y": 0.76, "w": 0.3, "h": 0.14}},
    {"type": "image", "asset": "logo", "box": {"x": 0.4, "y": 0.1, "w": 0.2, "h": 0.1}}
  ]
}
```

| Field | Rules |
|---|---|
| `canvas` | Whole pixels, at most 8192 per side and 40 MP in total. It may be omitted when the background is an asset, in which case the asset's size is used. |
| `background` | Either `{"color": "#RRGGBB"}` or `{"asset": "<id>"}`. An asset is scaled to cover the canvas and centre-cropped. |
| `box` | `x`, `y`, `w`, `h` as fractions of the canvas (0–1), entirely inside the canvas. Fractions let one layout scale across screen sizes. |
| `text` | At most 500 characters, with `{{variables}}`. `size` is a fraction of canvas height (for example 0.028). `align` is `left`, `center` or `right`, and the text is centred vertically in its box. Text that is too wide shrinks to fit. Font: `noto-sans` (bundled). |
| `qr` | `data` of at most 512 characters, with `{{variables}}`. Drawn square, centred in its box, with a quiet zone so it scans. `color` and `background` are optional. |
| `image` | `asset` id matching `^[a-z0-9_-]{1,64}$`, contained (never stretched) and centred in its box. |
| Colours | `#RRGGBB` or `#RRGGBBAA`. |
| Layers | At most 50, drawn in list order. |

**Variables** are `{{path}}` only: letters, digits, `_` and dots, with no filters and no code.

- **What prints:** only scalars (strings and numbers). A missing, empty or non-scalar value (a dict or list) renders as nothing, never as the literal `{{...}}` or a whole data subtree, and `lint` reports it.
- **Length caps:** each value is capped at 200 characters, and the final text at 500.

**Output** is an RGB image. Transparent areas render black.

- **Deterministic:** for a given Pillow version, the same template, values and assets always give the same pixels. Text uses Pillow's BASIC layout engine, the Regular instance of the bundled font, and whole-pixel positions.
- **Pinning:** pin Pillow exactly where byte-identical output across hosts matters.

## Limits (templates are untrusted input)

| Limit | Value |
|---|---|
| Canvas | at most 8192 px per side and 40 MP |
| Layers | at most 50 |
| Assets | PNG or JPEG only (never EPS/PS, which would invoke Ghostscript), checked for size before decoding, with an aspect ratio of at most 1:50. JPEG EXIF orientation is applied. Each asset is decoded once per render. |
| Text | shrinks to fit its box using a bounded number of measurements, and is drawn clipped to the box |
| QR | data that exceeds QR capacity raises `TemplateError` |
| Threads | fonts are created per render, so concurrent renders are safe |

## Font

`wallrender/fonts/NotoSans.ttf` is Noto Sans, licensed under the SIL Open Font License 1.1 (`wallrender/fonts/OFL.txt`). It covers Latin, Greek and Cyrillic. `lint` warns about any character it cannot draw, such as emoji or CJK.

## Try it

```bash
cd wallrender
uv venv && uv pip install -e . pytest
.venv/bin/python -m pytest
```

`examples/brander-basic.json` with `examples/sample-device.json` renders a sample iPhone lock-screen wallpaper.
