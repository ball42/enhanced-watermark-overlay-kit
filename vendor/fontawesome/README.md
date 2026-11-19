# Font Awesome Free 6.0.0 (solid icons only), full copy

Copied unchanged from the npm package `@fortawesome/fontawesome-free@6.0.0`: `css/fontawesome.min.css`,
`css/solid.min.css`, and the solid webfont in `webfonts/`. EWOK uses only the `fas` (solid) style, so the
regular and brands fonts are left out.

This folder is not served. The pages load a subset of it, holding only the icons they use, that
`scripts/subset_icons.py` writes to `static/vendor/fontawesome/`. Do not edit these files. To upgrade,
copy the same files from a newer package and run the script (`tests/test_offline_icons.py` checks every
`fa-*` name EWOK uses still exists).

Licence: icons CC BY 4.0, fonts SIL OFL 1.1, code MIT; see `LICENSE.txt` and
https://fontawesome.com/license/free. Copyright (c) Fonticons, Inc.
