# Vendored design-system files

`roster-web.css` and `roster-html.css` here are generated files from roster-bridge, which turns the
[@blakesteve/roster](https://github.com/blakesteve/roster) design tokens into plain CSS. The first line of each file names the roster
version and a content hash. Do not edit them by hand: replace them with newer generated copies.

Both pages (`templates/index.html` and `templates/template.html`) load them before `style.css`.
`style.css` maps EWOK's `--color-*`, `--shadow-*` and font variables onto these `--roster-*` tokens;
the Endor navbar colour is the one colour EWOK adds.

## Licences

- The generated CSS files are MIT licensed. They contain design-token values derived from
  @blakesteve/roster, used under the MIT License. Copyright (c) 2026 Blake Ball.
