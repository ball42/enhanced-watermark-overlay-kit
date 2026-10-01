"""`wallrender preview TEMPLATE VALUES -o OUT.png`: render a template with
sample device values and print what a designer should fix.

Exit codes: 0 written; 1 the template, values or an asset is unusable
(nothing written); 2 bad arguments; 3 written, but --strict and there
were warnings.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .render import lint, render
from .schema import ASSET_ID, TemplateError

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
        image = render(template, values, assets)
    except TemplateError as err:
        for problem in err.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    image.save(args.output)
    warnings = lint(template, values, assets)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"wrote {args.output} ({image.width}x{image.height}, {len(warnings)} warnings)")
    return 3 if args.strict and warnings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wallrender", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("preview", help="render a template with sample values")
    p.add_argument("template", help="template JSON")
    p.add_argument("values", help="sample device values JSON")
    p.add_argument("-o", "--output", required=True, help="PNG to write")
    p.add_argument("--assets", help="folder of <id>.png/.jpg assets (default: the template's folder)")
    p.add_argument("--strict", action="store_true", help="exit 3 if there are warnings")
    args = parser.parse_args(argv)
    return preview(args)


if __name__ == "__main__":
    sys.exit(main())
