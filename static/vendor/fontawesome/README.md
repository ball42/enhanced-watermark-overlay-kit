# Font Awesome Free 6.0.0, the icons EWOK uses

Made by `scripts/subset_icons.py` from the full copy in `vendor/fontawesome/` (not served), so both
pages show their icons without a network and load only the solid icons they name. `css/icons.min.css`
holds the base rules, the `@font-face` and one rule per icon; `webfonts/fa-solid-900.woff2` holds
just those glyphs.

Do not edit these files. After adding or removing an icon, run:

    uv run --with fonttools --with brotli python scripts/subset_icons.py

`tests/test_offline_icons.py` fails when the subset and the names in use differ.

Licence: icons CC BY 4.0, fonts SIL OFL 1.1, code MIT; see `LICENSE.txt` and
https://fontawesome.com/license/free. Copyright (c) Fonticons, Inc.
