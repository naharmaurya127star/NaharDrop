// Phase 5: dark mode toggle, persisted per-browser via localStorage.
(function () {
  function readSaved() {
    try {
      return localStorage.getItem("nd-theme");
    } catch (e) {
      return null;
    }
  }

  function save(theme) {
    try {
      localStorage.setItem("nd-theme", theme);
    } catch (e) {
      /* private browsing etc. - toggle still works for this page view */
    }
  }

  function isDark() {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const saved = readSaved();
    if (saved) document.documentElement.setAttribute("data-theme", saved);

    const btn = document.createElement("button");
    btn.className = "theme-toggle-btn";
    btn.textContent = isDark() ? "Light mode" : "Dark mode";
    btn.addEventListener("click", () => {
      const next = isDark() ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      save(next);
      btn.textContent = next === "dark" ? "Light mode" : "Dark mode";
    });
    document.body.appendChild(btn);
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        /* offline shell just won't be available - everything else still works */
      });
    });
  }
})();
