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
    document.querySelectorAll(".lang-toggle a").forEach(function (a) {
      a.addEventListener("click", function () {
        a.href = a.getAttribute("href").split("#")[0] + location.hash;
      });
    });
  });
})();
