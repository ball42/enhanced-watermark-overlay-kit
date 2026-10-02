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

## Preview from the command line

```bash
wallrender preview template.json sample-device.json -o preview.png
```

It renders the template with the sample values, writes the PNG, and prints warnings for:

- variables with no value;
- characters the font cannot draw;
- text that shrank below half its set size, or is cut off even at the minimum size;
- text whose contrast against what is behind it is below WCAG's 4.5:1, or 3:1 for large text.

Assets load from the template's folder (`<id>.png`, `.jpg` or `.jpeg`), or from `--assets DIR`. `--stress` also writes `OUT-long.png` and `OUT-empty.png`, with every variable the template uses set to a long, wide value and then to nothing. `--strict` exits 3 when there are warnings in any of them, for use in CI. Exit 1 means nothing was written, because the template, the values or an asset was unusable. `python -m wallrender` works too.

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
| `background` | Either `{"color": "#RRGGBB"}` or `{"asset": "<id>"}`. An asset is scaled to cover the canvas and center-cropped. |
| `box` | `x`, `y`, `w`, `h` as fractions of the canvas (0–1), entirely inside the canvas. Fractions let one layout scale across screen sizes. |
| `text` | At most 500 characters, with `{{variables}}`. `size` is a fraction of canvas height (for example 0.028). `align` is `left`, `center` or `right`, and applies to every line of multi-line text; the text block is centered vertically in its box. Text that does not fit is handled by the layer's overflow policy (below). Font: `noto-sans` (bundled). |
| `qr` | `data` of at most 512 characters, with `{{variables}}`. Drawn square, centered in its box, with a quiet zone so it scans. `color` and `background` are optional. `hide_if_empty` works as for text. |
| `image` | `asset` id matching `^[a-z0-9_-]{1,64}$`, contained (never stretched) and centered in its box. |
| Colors | `#RRGGBB` or `#RRGGBBAA`. |
| Layers | At most 50, drawn in list order. |

**Long and empty values.** Each text layer chooses what happens:

| Field | Effect |
|---|---|
| `overflow: "shrink"` | The default. The text shrinks until it fits the box. Below `min_size` it is cut off at the box edge. |
| `overflow: "ellipsis"` | The text shrinks down to `min_size`, then is shortened with "…" so it fits the width. Without `min_size` it keeps its set size and is only shortened. |
| `min_size` | The smallest font size allowed, as a fraction of canvas height, at most `size`. |
| `hide_if_empty: true` | Skip the layer when any of its variables has no value, so `"Asset {{asset_tag}}"` disappears instead of printing a bare "Asset". QR layers accept it too. |

**Variables** are `{{path}}` only: letters, digits, `_` and dots, with no filters and no code.

- **What prints:** only scalars (strings and numbers). A missing, empty or non-scalar value (a dict or list) renders as nothing, never as the literal `{{...}}` or a whole data subtree, and `lint` reports it.
- **Length caps:** each value is capped at 200 characters, and the final text at 500.

**Output** is an RGB image. Transparent areas render black.

- **Deterministic:** for a given Pillow version, the same template, values and assets always give the same pixels. Text uses Pillow's BASIC layout engine, the Regular instance of the bundled font, and whole-pixel positions.
- **Pinning:** pin Pillow exactly where byte-identical output across hosts matters.

## Personal fields

A template may print who the device belongs to, as `{{user.real_name}}`, `{{user.username}}` and `{{user.email}}`, only if it sets `"person_fields": true`. `validate` rejects `user.*` in text otherwise, and **always** rejects it in QR codes, because anyone can scan them. JAWA Brander adds a second lock: it fills `user.*` only when the admin also allows personal fields for that Brander. Otherwise the fields render empty. See JAWA ADR-0013.

## Role variants

One template can change its background and wording by the device's role:

```json
"roles": {
  "attribute": "Jamf Setup Role",
  "variants": {
    "nursing": {"background": {"asset": "nursing"}, "values": {"title": "Nursing"}},
    "videoconferencing": {"values": {"title": "Video calls"}}
  },
  "empty": {"values": {"title": "Please open the Setup app"}},
  "default": {"values": {"title": "General use"}}
}
```

- **Where the role comes from.** Pass it as `values["role"]`, a string. JAWA Brander reads it from the extension attribute named in `attribute`.
- **Matching.** The role is lowercased with spaces removed (`"Video Conferencing"` becomes `videoconferencing`), the way Brander already matches role images, so variant keys use that form.
- **Which variant applies.** The matching variant applies. With no role, `empty` applies; with any other role, `default`.
- **What a variant can change.** Its `background` replaces the template's. Its `values` print as `{{role.<name>}}`, and `{{role.name}}` is the role as given. Layers don't change, so `hide_if_empty` and overflow still apply.
- **Limits.** At most 50 variants, each with at most 20 values of up to 200 characters. `lint` notes when a role falls back to the default or the empty variant.

## Devices: crops and covered areas

iOS scales a wallpaper to fill the screen and centers it, so a template whose shape differs from the screen loses its edges. On a 2048×2732 iPad, a 1290×2796 iPhone template keeps only the middle 62% of its height. `wallrender.devices` models this:

- `device_profiles()`: iPhone 6.7-inch, 6.1-inch and SE, and iPad Pro 12.9-inch, 11-inch and 10.9-inch, from `device_profiles.json`. Each has a screen size, whether it rotates, and the approximate areas the clock and controls (lock screen) or the status bar and dock (home screen) cover.
- `visible_region(canvas, screen)`: the part of the canvas a screen shows.
- `fit_warnings(template, canvas, device_ids, "lock" | "home")`: layers that a device crops off, or that sit under its clock, controls or dock, in each orientation.

A square canvas with everything in its center 75% survives both iPad orientations. The covered areas are approximate, so check a new device or iOS release on hardware.

## Limits (templates are untrusted input)

| Limit | Value |
|---|---|
| Canvas | at most 8192 px per side and 40 MP |
| Layers | at most 50 |
| Assets | PNG or JPEG only (never EPS/PS, which would invoke Ghostscript), checked for size before decoding, with an aspect ratio of at most 1:50. JPEG EXIF orientation is applied. Each asset is decoded once per render. |
| Text | shrinks to fit its box using a bounded number of measurements, and is drawn clipped to the box |
| QR | data longer than 512 characters after substitution raises `TemplateError`: never silently truncated, which would encode a different code |
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
