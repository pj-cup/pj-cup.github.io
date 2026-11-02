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

    // Fade the right edge of a table while more columns are scrolled out of view.
    var scrollers = document.querySelectorAll(".table-scroll");
    function updateFade(el) {
      el.classList.toggle("more-right", el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
    }
    Array.prototype.forEach.call(scrollers, function (el) {
      updateFade(el);
      el.addEventListener("scroll", function () { updateFade(el); }, { passive: true });
    });
    window.addEventListener("resize", function () {
      Array.prototype.forEach.call(scrollers, updateFade);
    });

    // Head-to-head crosshair: mark the hovered cell's column (row hover is plain CSS).
    var grid = document.querySelector("table.h2h");
    if (grid) {
      var marked = [];
      function clearMarks() {
        marked.forEach(function (c) { c.classList.remove("xh"); });
        marked = [];
      }
      grid.addEventListener("mouseover", function (e) {
        var cell = e.target.closest("td, th");
        clearMarks();
        if (!cell || cell.cellIndex < 1) return;
        Array.prototype.forEach.call(grid.rows, function (row) {
          var c = row.cells[cell.cellIndex];
          if (c) { c.classList.add("xh"); marked.push(c); }
        });
      });
      grid.addEventListener("mouseleave", clearMarks);
    }
  });
})();
