/* roster-bridge 0.1.0 from @blakesteve/roster 5.17.0 theme.js sha256:6d87f5a59e3b */
/* Load in <head> without defer, so .dark is set before first paint:
 *   <script src="theme.js"> with its end tag, or paste this file inside a script element.
 * <button data-roster-theme-toggle> toggles light/dark (aria-pressed = dark). data-roster-theme-toggle="light",
 * "dark" or "system" picks that choice (aria-pressed = it is the current one; rb.theme_switch renders all three).
 * "system", or rosterTheme.set("system"), forgets the saved choice and follows the OS again. Other tabs follow along.
 * Each change dispatches "roster-theme-change" on document, with detail.theme "light" or "dark". */
(function () {
  var KEY = "roster-theme", ATTR = "data-roster-theme-toggle", root = document.documentElement, SEL = "[" + ATTR + "]";
  function stored() { try { var v = localStorage.getItem(KEY); return v === "dark" || v === "light" ? v : null; } catch (e) { return null; } }
  var mq = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function system() { return mq && mq.matches ? "dark" : "light"; }
  function sync() {
    var dark = root.classList.contains("dark"), choice = stored() || "system", buttons = document.querySelectorAll(SEL);
    for (var i = 0; i < buttons.length; i++) {
      var v = buttons[i].getAttribute(ATTR);
      buttons[i].setAttribute("aria-pressed", String(v ? v === choice : dark));
    }
  }
  function apply(theme) {
    root.classList.toggle("dark", theme === "dark");
    sync();
    document.dispatchEvent(new CustomEvent("roster-theme-change", { detail: { theme: theme } }));
  }
  function set(theme) {
    if (theme !== "dark" && theme !== "light") theme = "system";
    try { if (theme === "system") localStorage.removeItem(KEY); else localStorage.setItem(KEY, theme); } catch (e) {}
    apply(theme === "system" ? system() : theme);
  }
  root.classList.toggle("dark", (stored() || system()) === "dark");
  if (mq && mq.addEventListener) mq.addEventListener("change", function () { if (!stored()) apply(system()); });
  window.addEventListener("storage", function (e) { if (e.key === KEY || e.key === null) apply(stored() || system()); });
  function bind() {
    sync();
    document.addEventListener("htmx:afterSettle", sync);
    document.addEventListener("click", function (e) {
      var t = e.target && e.target.closest ? e.target.closest(SEL) : null;
      if (t) set(t.getAttribute(ATTR) || (root.classList.contains("dark") ? "light" : "dark"));
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind); else bind();
  window.rosterTheme = { set: set };
})();
