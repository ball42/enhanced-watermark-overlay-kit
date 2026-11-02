# Vendored design-system files

`roster-web.css`, `roster-html.css` and `icons.svg` here, and `static/js/vendor/roster-theme.js`, are
generated files from roster-bridge, which turns the
[@blakesteve/roster](https://github.com/blakesteve/roster) design tokens into plain CSS, an icon sprite
and a small theme script. The first line of each file names the roster version and a content hash.
Do not edit them by hand: replace them with newer generated copies.

Both pages (`templates/index.html` and `templates/template.html`) load them before `style.css`.
`style.css` maps EWOK's `--color-*`, `--shadow-*` and font variables onto these `--roster-*` tokens,
for light and for `.dark`; the Endor navbar colour is the one colour EWOK adds. `roster-theme.js`
follows the OS setting until the navbar toggle saves a choice (the `roster-theme` key).

## Licences

- The generated CSS and script are MIT licensed. They contain design-token values derived from
  @blakesteve/roster, used under the MIT License. Copyright (c) 2026 Blake Ball.
- `icons.svg` contains icons from Font Awesome Free (@fortawesome/free-solid-svg-icons,
  https://fontawesome.com), Copyright (c) Fonticons, Inc. The icons are licensed under CC BY 4.0
  (https://creativecommons.org/licenses/by/4.0/); see https://fontawesome.com/license/free.
