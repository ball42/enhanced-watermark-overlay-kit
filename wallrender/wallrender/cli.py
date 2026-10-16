"""`wallrender preview TEMPLATE VALUES -o OUT.png`: render a template with
sample device values and print what a designer should fix.
`wallrender devices`: list the device ids that --devices takes.

Exit codes: 0 written; 1 the template, values or an asset is unusable
(nothing written); 2 bad arguments; 3 written, but --strict and there
were warnings (device warnings included).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from .devices import MAX_DEVICE_IDS, device_profiles, fit_warnings
from .render import render_with_lint
from .schema import ASSET_ID, TemplateError, variables_in

STRESS_VALUE = "W" * 48  # wide glyphs: the worst case for one line

ASSET_EXTENSIONS = ("png", "jpg", "jpeg")


def folder_assets(folder: str):
    """Resolve asset ids to <folder>/<id>.png|jpg|jpeg, never outside it."""
    root = os.path.realpath(folder)

    def resolve(asset_id: str) -> bytes:
        if ASSET_ID.fullmatch(asset_id):
            for ext in ASSET_EXTENSIONS:
                path = os.path.realpath(os.path.join(root, f"{asset_id}.{ext}"))
                if path.startswith(root + os.sep) and os.path.isfile(path):
                    with open(path, "rb") as handle:
                        return handle.read()
        raise KeyError(asset_id)

    return resolve


def _load_json(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


LAYER_REF = re.compile(r"\blayer (\d+)")
LABEL_CHARS = 40


def _describe(layer) -> str:
    """A layer as the designer's layer list names it: its type and content."""
    if not isinstance(layer, dict) or not isinstance(layer.get("type"), str):
        return ""
    kind = layer["type"]
    detail = {"text": layer.get("text"), "qr": layer.get("data"),
              "image": layer.get("asset")}.get(kind)
    if not isinstance(detail, str) or not detail:
        return f" ({kind})"
    detail = " ".join(detail.split())
    if len(detail) > LABEL_CHARS:
        detail = detail[:LABEL_CHARS - 1] + "\u2026"
    return f" ({kind}: {detail})"


def _label(template, message: str) -> str:
    """Number layers from 1, as the designer does, and say which layer it is.
    The renderer's own messages stay 0-based (JAWA reads them)."""
    layers = template.get("layers") if isinstance(template, dict) else None
    layers = layers if isinstance(layers, list) else []

    def one(match):
        i = int(match.group(1))
        return f"layer {i + 1}" + (_describe(layers[i]) if i < len(layers) else "")

    return LAYER_REF.sub(one, message)


def _paths(template: dict) -> list[str]:
    found: list[str] = []
    for layer in template.get("layers", []):
        for key in ("text", "data"):
            if isinstance(layer.get(key), str):
                found.extend(variables_in(layer[key]))
    return list(dict.fromkeys(found))


def stress_values(template: dict) -> dict:
    """Every variable the template uses, set to a long, wide value."""
    values: dict = {}
    if "roles" in template:
        values["role"] = STRESS_VALUE  # an unknown, very long role: the default variant
    for path in _paths(template):
        if "roles" in template and (path == "role" or path.startswith("role.")):
            continue  # role.* comes from the variant, not from the device
        node = values
        *parents, leaf = path.split(".")
        for part in parents:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                break
        else:
            node[leaf] = STRESS_VALUE
    return values


MAX_STRESS_ROLES = 10


def role_keys(template: dict) -> list:
    """Role variant keys to stress-render, at most MAX_STRESS_ROLES."""
    variants = (template.get("roles") or {}).get("variants") or {}
    return list(variants)[:MAX_STRESS_ROLES]


def _variant(template, values, assets, output: str, label: str) -> int:
    """Render one stress variant; returns how many problems it showed."""
    try:
        image, warnings = render_with_lint(template, values, assets)
    except TemplateError as err:
        for problem in err.problems:
            print(f"[{label}] error: {_label(template, problem)}", file=sys.stderr)
        return len(err.problems)
    image.save(output)
    for warning in warnings:
        print(f"[{label}] warning: {_label(template, warning)}", file=sys.stderr)
    print(f"wrote {output} ({label} values, {len(warnings)} warnings)")
    return len(warnings)


def _device_ids(text: str) -> list[str]:
    """--devices: comma-separated profile ids, or "all"."""
    known = [p["id"] for p in device_profiles()]
    if text.strip() == "all":
        return known
    ids = [part.strip() for part in text.split(",") if part.strip()]
    unknown = [i for i in ids if i not in known]
    if unknown or not ids:
        raise argparse.ArgumentTypeError(
            f"unknown device {', '.join(unknown) or '(none given)'}; "
            f"`wallrender devices` lists: {', '.join(known)}")
    return ids[:MAX_DEVICE_IDS]


def _screens(template, choice) -> list[str]:
    """--screen, else the template's own screen ("both" checks each)."""
    screen = choice or (template.get("screen") if isinstance(template, dict) else None)
    return ["lock", "home"] if screen == "both" else [screen if screen == "home" else "lock"]


def devices(_args: argparse.Namespace) -> int:
    for profile in device_profiles():
        print(f"{profile['id']:<12} {profile['name']}")
    return 0


def preview(args: argparse.Namespace) -> int:
    loaded = []
    for path in (args.template, args.values):
        try:
            loaded.append(_load_json(path))
        except (OSError, ValueError) as err:
            print(f"error: {path}: {err}", file=sys.stderr)
            return 1
    template, values = loaded
    assets = folder_assets(args.assets or os.path.dirname(os.path.abspath(args.template)))
    try:
        image, warnings = render_with_lint(template, values, assets)
    except TemplateError as err:
        for problem in err.problems:
            print(f"error: {_label(template, problem)}", file=sys.stderr)
        return 1
    image.save(args.output)
    if args.devices:
        screens = _screens(template, args.screen)
        for screen in screens:
            suffix = f", {screen} screen" if len(screens) > 1 else ""
            warnings += [w + suffix for w in fit_warnings(template, image.size, args.devices, screen)]
    for warning in warnings:
        print(f"warning: {_label(template, warning)}", file=sys.stderr)
    print(f"wrote {args.output} ({image.width}x{image.height}, {len(warnings)} warnings)")
    problems = len(warnings)
    if args.stress:
        stem, ext = os.path.splitext(args.output)
        problems += _variant(template, stress_values(template), assets, f"{stem}-long{ext}", "long")
        problems += _variant(template, {}, assets, f"{stem}-empty{ext}", "empty")
        for key in role_keys(template):
            problems += _variant(template, dict(values, role=key), assets,
                                 f"{stem}-role-{key}{ext}", f"role {key}")
    return 3 if args.strict and problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wallrender", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("preview", help="render a template with sample values")
    p.add_argument("template", help="template JSON")
    p.add_argument("values", help="sample device values JSON")
    p.add_argument("-o", "--output", required=True, help="PNG to write")
    p.add_argument("--assets", help="folder of <id>.png/.jpg assets (default: the template's folder)")
    p.add_argument("--stress", action="store_true",
                   help="also render OUT-long, OUT-empty and one OUT-role-<key> per role variant: "
                        "every variable long, then empty, then each role")
    p.add_argument("--devices", type=_device_ids, metavar="IDS",
                   help="also check crops and covered areas on these devices: comma-separated "
                        "ids from `wallrender devices`, or all")
    p.add_argument("--screen", choices=("lock", "home"),
                   help="screen for --devices (default: the template's screen, else lock)")
    p.add_argument("--strict", action="store_true",
                   help="exit 3 if there are warnings, device warnings included")
    p.set_defaults(run=preview)
    d = commands.add_parser("devices", help="list the device ids that --devices takes")
    d.set_defaults(run=devices)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
