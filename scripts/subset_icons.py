"""Make the Font Awesome subset the pages load: only the icons EWOK uses.

The full Font Awesome Free 6.0.0 copy stays in vendor/fontawesome/ (not
served). This writes static/vendor/fontawesome/css/icons.min.css and
webfonts/fa-solid-900.woff2 holding just the fa-* names found in templates/
and static/js/. Run it after adding or removing an icon:

    uv run --with fonttools --with brotli python scripts/subset_icons.py

tests/test_offline_icons.py fails when the subset and the names in use differ.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "vendor" / "fontawesome"
OUT = ROOT / "static" / "vendor" / "fontawesome"
SOURCES = [*(ROOT / "templates").glob("*.html"), *(ROOT / "static" / "js").glob("*.js")]
NAME = re.compile(r"\bfa-[a-z0-9]+(?:-[a-z0-9]+)*\b")
# The rules every icon needs: the font-family and the inline-block base.
BASE_SELECTORS = {".fa", ".fas"}


def used_names() -> set[str]:
    names: set[str] = set()
    for source in SOURCES:
        names |= set(NAME.findall(source.read_text(encoding="utf-8")))
    return names


def rules(css: str) -> list[tuple[str, str]]:
    """Top-level (selector, body) pairs; at-rules (keyframes, media) are dropped."""
    body = css[css.index("*/") + 2:]
    out = []
    for match in re.finditer(r"(@[^{]+\{(?:[^{}]*\{[^}]*\})*[^}]*\})|([^{}]+)\{([^}]*)\}", body):
        if match.group(2):
            out.append((match.group(2).strip(), match.group(3)))
    return out


def subset_css(full_css: str, solid_css: str, used: set[str]) -> tuple[str, set[int]]:
    header = full_css[:full_css.index("*/") + 2]
    keep, codepoints = [], set()
    for selector, body in rules(full_css):
        parts = [s.strip() for s in selector.split(",")]
        if body.startswith("content:"):
            mine = [s for s in parts if s.endswith(":before") and s[1:-len(":before")] in used]
            if mine:
                keep.append(f"{','.join(mine)}{{{body}}}")
                code = re.search(r'content:"\\([0-9a-f]+)"', body).group(1)
                codepoints.add(int(code, 16))
        elif any(p in BASE_SELECTORS or p[1:] in used for p in parts):
            keep.append(f"{selector}{{{body}}}")
    # solid.min.css: the face (woff2 only; every browser EWOK supports reads it) and .fas.
    face = re.sub(r",url\(\.\./webfonts/fa-solid-900\.ttf\) format\(\"truetype\"\)", "", solid_css[solid_css.index("*/") + 2:])
    lines = [header, f"/* Subset for EWOK: {len(codepoints)} icons. Made by scripts/subset_icons.py; do not edit. */",
             face.strip(), "".join(keep)]
    return "\n".join(lines) + "\n", codepoints


def subset_font(codepoints: set[int], out: Path) -> None:
    from fontTools import subset

    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = []
    options.name_IDs = ["*"]  # keeps the licence and copyright strings
    options.notdef_outline = True
    font = subset.load_font(str(FULL / "webfonts" / "fa-solid-900.ttf"), options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(codepoints))
    subsetter.subset(font)
    subset.save_font(font, str(out), options)


def main() -> int:
    used = used_names()
    css, codepoints = subset_css((FULL / "css" / "fontawesome.min.css").read_text(encoding="utf-8"),
                                 (FULL / "css" / "solid.min.css").read_text(encoding="utf-8"), used)
    (OUT / "css").mkdir(parents=True, exist_ok=True)
    (OUT / "webfonts").mkdir(parents=True, exist_ok=True)
    font = OUT / "webfonts" / "fa-solid-900.woff2"
    subset_font(codepoints, font)
    # Static files are cached for an hour: the font's URL carries its hash,
    # so a new subset is fetched at once.
    version = hashlib.sha256(font.read_bytes()).hexdigest()[:12]
    css = css.replace("fa-solid-900.woff2)", f"fa-solid-900.woff2?v={version})")
    (OUT / "css" / "icons.min.css").write_text(css, encoding="utf-8")
    shutil.copy(FULL / "LICENSE.txt", OUT / "LICENSE.txt")
    size = (OUT / "css" / "icons.min.css").stat().st_size + (OUT / "webfonts" / "fa-solid-900.woff2").stat().st_size
    print(f"{len(codepoints)} icons, {size:,} bytes of CSS and font")
    return 0


if __name__ == "__main__":
    sys.exit(main())
