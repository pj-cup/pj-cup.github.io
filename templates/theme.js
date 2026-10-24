(function () {
  function getStored() {
    try {
      return localStorage.getItem("theme");
    } catch (e) {
      return null;
    }
  }

  function setStored(value) {
    try {
      localStorage.setItem("theme", value);
    } catch (e) {}
  }

  function systemPrefersDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function currentTheme() {
    var stored = getStored();
    if (stored === "light" || stored === "dark") return stored;
    return systemPrefersDark() ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(currentTheme());
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var next = currentTheme() === "dark" ? "light" : "dark";
        setStored(next);
        applyTheme(next);
      });
    }

    // Keep an open player card / compare (#player-x, #compare-a-vs-b) when switching language.
    // Delegated, so it also covers the copies player-card.js puts inside the dialogs.
    function keepHash(e) {
      var a = e.target.closest && e.target.closest(".lang-toggle a");
      if (a) a.href = a.getAttribute("href").split("#")[0] + location.hash;
    }
    document.addEventListener("click", keepHash);
    document.addEventListener("auxclick", keepHash);
  });
})();
