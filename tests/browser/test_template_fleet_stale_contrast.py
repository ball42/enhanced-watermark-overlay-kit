"""An out-of-date device check stays readable: no fade, a cue that is not opacity."""

from importlib import resources

import pytest

from .test_template_fleet import load_csv

AXE = resources.files("axe_playwright_python").joinpath("axe.min.js").read_text()

# Text and its effective background, with every ancestor's opacity applied,
# for each visible text element in the summary and the sheet. Returns the
# lowest contrast ratio found and where.
WORST_CONTRAST = """() => {
  // rgb()/rgba() in 0-255, or color(srgb r g b / a) in 0-1 (from color-mix).
  const rgb = (s) => {
    const n = (s.match(/[\\d.]+/g) || []).map(Number);
    if (!s.startsWith('color(')) return n;
    return n.map((c, i) => (i < 3 ? c * 255 : c));
  };
  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  // Composite translucent backgrounds up to the first opaque one.
  const background = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const c = rgb(getComputedStyle(n).backgroundColor);
      const a = c.length === 4 ? c[3] : 1;
      if (a > 0) layers.push([c.slice(0, 3), a]);
      if (a >= 1) break;
    }
    let out = [255, 255, 255];
    for (const [c, a] of layers.reverse()) out = c.map((v, i) => v * a + out[i] * (1 - a));
    return out;
  };
  const opacity = (el) => {
    let o = 1;
    for (let n = el; n; n = n.parentElement) o *= Number(getComputedStyle(n).opacity);
    return o;
  };
  let worst = { ratio: 99, text: '' };
  const roots = [document.querySelector('#fleetSummary'), document.querySelector('#fleetSheet')];
  for (const root of roots) {
    for (const el of root.querySelectorAll('*')) {
      const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (!own || !el.getClientRects().length) continue;
      const bg = background(el);
      const a = opacity(el);
      const fg = rgb(getComputedStyle(el).color).slice(0, 3).map((c, i) => c * a + bg[i] * (1 - a));
      const [l1, l2] = [lum(fg), lum(bg)].sort((x, y) => y - x);
      const ratio = (l1 + 0.05) / (l2 + 0.05);
      if (ratio < worst.ratio) worst = { ratio, text: el.textContent.trim().slice(0, 60), fg: fg.map(Math.round), bg, el: el.tagName + '.' + el.className };
    }
  }
  return worst;
}"""


def make_stale(page, tmp_path):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    load_csv(page, tmp_path)
    page.click('[aria-label="Delete layer 2"]')
    page.wait_for_selector("#fleetStale:not([hidden])")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_stale_results_keep_full_contrast(page, tmp_path, scheme):
    page.emulate_media(color_scheme=scheme)
    make_stale(page, tmp_path)
    assert ("dark" in (page.get_attribute("html", "class") or "")) == (scheme == "dark")

    worst = page.evaluate(WORST_CONTRAST)
    assert worst["ratio"] >= 4.5, worst

    page.add_script_tag(content=AXE)
    result = page.evaluate(
        "async () => (await axe.run(document, {runOnly: ['color-contrast']}))"
        ".violations.flatMap((v) => v.nodes.map((n) => n.target.join(' ')))")
    assert result == []


def test_stale_results_are_marked_without_fading(page, tmp_path):
    make_stale(page, tmp_path)
    assert page.evaluate("getComputedStyle(document.querySelector('.tpl-fleet-body')).opacity") == "1"
    assert page.evaluate("getComputedStyle(document.querySelector('#fleetSheet')).opacity") == "1"
    # The hero number carries the word, and the report's frame turns dashed.
    tag = page.locator("#fleetFitStale")
    assert tag.is_visible()
    assert tag.text_content().strip() == "Out of date"
    assert page.evaluate(
        "getComputedStyle(document.querySelector('#fleetSummary')).borderTopStyle") == "dashed"

    page.click("#fleetStaleRecheck")
    page.wait_for_selector("#fleetStale", state="hidden")
    assert tag.is_hidden()
    assert page.evaluate(
        "getComputedStyle(document.querySelector('#fleetSummary')).borderTopStyle") == "solid"
