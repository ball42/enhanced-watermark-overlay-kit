"""Template designer: the preview speaks only when its outcome changes,
not on every render while the user types."""

# Every live region on the page, and each time its text changes.
WATCH = """() => {
  window.__spoken = [];
  const regions = document.querySelectorAll('[aria-live], [role="status"], [role="alert"]');
  const obs = new MutationObserver(() => regions.forEach((r, i) => {
    const t = r.textContent.trim();
    if (t !== (r.__last ?? '')) window.__spoken.push(t);
    r.__last = t;
  }));
  regions.forEach((r) => { r.__last = r.textContent.trim();
    obs.observe(r, { childList: true, subtree: true, characterData: true }); });
  return regions.length;
}"""


def renders_settle(page):
    page.wait_for_function("!document.querySelector('.tpl-preview').classList.contains('is-stale')")
    page.wait_for_function("!document.querySelector('#previewStatus').textContent.startsWith('Rendering')")


def test_typing_says_nothing_and_a_new_warning_says_it_once(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    renders_settle(page)
    assert page.inner_text("#previewAnnounce") == "Preview: no warnings."
    assert page.locator("[aria-live]#previewStatus, [aria-live]#warningList, [aria-live]#warningCount").count() == 0

    page.evaluate(WATCH)
    renders = []
    page.on("request", lambda r: renders.append(r) if r.url.endswith("/api/template/preview") else None)
    page.focus("#propText")
    page.keyboard.press("End")
    for ch in " Lab":
        page.keyboard.type(ch)
        page.wait_for_timeout(500)  # past the 300 ms debounce: one render each
    renders_settle(page)
    assert len(renders) >= 4
    assert page.evaluate("window.__spoken") == []

    # Text the colour of the background: a low-contrast warning.
    page.evaluate("""() => { const c = document.querySelector('#propColor');
      c.value = document.querySelector('#bgColor').value;
      c.dispatchEvent(new Event('input', { bubbles: true }));
      c.dispatchEvent(new Event('change', { bubbles: true })); }""")
    page.wait_for_function("document.querySelector('#warningList').textContent.includes('low contrast')")
    renders_settle(page)
    assert page.evaluate("window.__spoken") == ["Preview: 1 warning."]
