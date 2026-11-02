/* roster-bridge 0.1.0 from @blakesteve/roster 5.17.0 theme.js sha256:127c5845f3a6 */
/* Load in <head> without defer, so .dark is set before first paint:
 *   <script src="theme.js"></script>
 * Any <button data-roster-theme-toggle> toggles the theme; aria-pressed follows it, also after HTMX swaps.
 * Each change dispatches "roster-theme-change" on document, with detail.theme "light" or "dark". */
(function () {
  var KEY = "roster-theme", root = document.documentElement, SEL = "[data-roster-theme-toggle]";
  function stored() { try { var v = localStorage.getItem(KEY); return v === "dark" || v === "light" ? v : null; } catch (e) { return null; } }
  var mq = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function system() { return mq && mq.matches ? "dark" : "light"; }
  function sync() {
    var dark = root.classList.contains("dark"), buttons = document.querySelectorAll(SEL);
    for (var i = 0; i < buttons.length; i++) buttons[i].setAttribute("aria-pressed", String(dark));
  }
  function apply(theme) {
    root.classList.toggle("dark", theme === "dark");
    sync();
    document.dispatchEvent(new CustomEvent("roster-theme-change", { detail: { theme: theme } }));
  }
  function set(theme) {
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    apply(theme);
  }
  root.classList.toggle("dark", (stored() || system()) === "dark");
  if (mq && mq.addEventListener) mq.addEventListener("change", function () { if (!stored()) apply(system()); });
  function bind() {
    sync();
    document.addEventListener("htmx:afterSettle", sync);
    document.addEventListener("click", function (e) {
      var t = e.target && e.target.closest ? e.target.closest(SEL) : null;
      if (t) set(root.classList.contains("dark") ? "light" : "dark");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind); else bind();
  window.rosterTheme = { set: set };
})();
