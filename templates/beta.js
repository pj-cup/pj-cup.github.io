(function () {
  "use strict";

  var root = document.documentElement;
  root.setAttribute("data-boot", "1"); // tells the head fallback that this script is alive

  var mq = function (q) { return !!(window.matchMedia && window.matchMedia(q).matches); };
  var reduce = mq("(prefers-reduced-motion: reduce)");
  var finePointer = mq("(hover: hover) and (pointer: fine)");

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  /* ---------- head-to-head crosshair (no motion, always on) ---------- */

  (function () {
    var table = $(".h2h");
    if (!table) return;
    var lit = [];
    var hit = null;

    function clear() {
      lit.forEach(function (el) { el.classList.remove("hl"); });
      lit = [];
      if (hit) { hit.classList.remove("hit"); hit = null; }
    }

    table.addEventListener("mouseover", function (e) {
      var cell = e.target.closest("td, th");
      if (!cell || !table.contains(cell)) return;
      clear();
      var col = cell.cellIndex;
      Array.prototype.forEach.call(cell.parentElement.cells, function (x) { x.classList.add("hl"); lit.push(x); });
      Array.prototype.forEach.call(table.rows, function (row) {
        var x = row.cells[col];
        if (x) { x.classList.add("hl"); lit.push(x); }
      });
      if (cell.tagName === "TD") { cell.classList.add("hit"); hit = cell; }
    });
    table.addEventListener("mouseleave", clear);
  })();

  /* ---------- canvas effects: confetti burst + cursor ball trail ---------- */

  var canvas = $("#fx");
  var ctx = canvas && canvas.getContext ? canvas.getContext("2d") : null;
  var parts = [];
  var running = false;
  var last = 0;
  var W = 0;
  var H = 0;
  var MAX_PARTS = 450;

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function loop(ts) {
    var dt = Math.min((ts - last) / 1000, 0.05);
    last = ts;
    ctx.clearRect(0, 0, W, H);
    for (var i = parts.length - 1; i >= 0; i--) {
      var p = parts[i];
      p.life -= dt;
      if (p.life <= 0 || p.y > H + 30) { parts.splice(i, 1); continue; }
      if (p.t === "c") {
        p.vy += 900 * dt;
        p.vx *= 0.995;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.r += p.vr * dt;
        ctx.save();
        ctx.globalAlpha = Math.min(1, p.life);
        ctx.translate(p.x, p.y);
        ctx.rotate(p.r);
        ctx.fillStyle = p.c;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      } else {
        var k = p.life / p.max;
        ctx.globalAlpha = k * 0.7;
        ctx.fillStyle = "#d7f13a";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * k, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    if (parts.length) {
      requestAnimationFrame(loop);
    } else {
      running = false;
      ctx.clearRect(0, 0, W, H);
    }
  }

  function kick() {
    if (running) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(loop);
  }

  function burst() {
    if (!ctx) return;
    var target = $(".card.leader .pts");
    var r = target ? target.getBoundingClientRect() : { left: W / 2, top: H / 3, width: 0, height: 0 };
    var cx = r.left + r.width / 2;
    var cy = Math.min(Math.max(r.top + r.height / 2, 40), H - 40);
    var colors = ["#d7f13a", "#ffffff", "#34d27b", "#f5c542", "#1c7a3e"];
    for (var i = 0; i < 110 && parts.length < MAX_PARTS; i++) {
      var a = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.3;
      var s = 280 + Math.random() * 520;
      parts.push({
        t: "c", x: cx, y: cy,
        vx: Math.cos(a) * s, vy: Math.sin(a) * s,
        r: Math.random() * 6.28, vr: (Math.random() - 0.5) * 14,
        w: 5 + Math.random() * 6, h: 3 + Math.random() * 5,
        c: colors[i % colors.length],
        life: 2.2 + Math.random() * 1.2
      });
    }
    kick();
  }

  /* ---------- sections: reveal on scroll ---------- */

  function countUp(section) {
    if (reduce) return;
    $$(".count", section).forEach(function (el, i) {
      var to = parseInt(el.getAttribute("data-to"), 10);
      if (isNaN(to) || to === 0) return;
      var delay = 300 + i * 70;
      var dur = 1300;
      var t0 = null;
      el.textContent = "0";
      // Never leave a wrong number on screen if animation frames stall.
      setTimeout(function () { el.textContent = String(to); }, delay + dur + 500);
      function step(ts) {
        if (t0 === null) t0 = ts + delay;
        var p = Math.min(Math.max((ts - t0) / dur, 0), 1);
        el.textContent = String(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  function show(section) {
    section.classList.add("in");
    if (section.id === "standings") {
      countUp(section);
      if (!reduce) setTimeout(burst, 900);
    }
  }

  function revealSections() {
    var sections = $$(".reveal");
    if (reduce || !("IntersectionObserver" in window)) {
      sections.forEach(show);
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { io.unobserve(en.target); show(en.target); }
      });
    }, { threshold: 0.12 });
    sections.forEach(function (s) { io.observe(s); });

    // Safety net: some embedded/headless contexts never deliver IntersectionObserver
    // callbacks, which would leave the page blank. Reveal whatever is on screen.
    setTimeout(function () {
      sections.forEach(function (s) {
        if (s.classList.contains("in")) return;
        var r = s.getBoundingClientRect();
        if (r.top < window.innerHeight && r.bottom > 0) { io.unobserve(s); show(s); }
      });
    }, 1500);
  }

  /* ---------- ambient: drifting balls, parallax, tilt, cursor trail ---------- */

  function ambient() {
    if (reduce) return;

    // [left %, top %, size px, parallax factor, drift seconds, delay seconds]
    var specs = [
      [6, 12, 46, -0.05, 18, 0], [88, 8, 30, -0.12, 22, -4],
      [14, 58, 70, -0.02, 26, -9], [80, 46, 54, -0.08, 20, -2],
      [48, 82, 36, -0.14, 24, -12], [92, 78, 64, -0.03, 28, -6],
      [30, 30, 26, -0.16, 19, -8], [62, 18, 40, -0.10, 23, -14]
    ];
    var layer = $(".balls");
    if (layer) {
      specs.forEach(function (s) {
        var wrap = document.createElement("div");
        wrap.className = "ball";
        wrap.style.left = s[0] + "%";
        wrap.style.top = s[1] + "%";
        wrap.style.setProperty("--k", s[3]);
        var b = document.createElement("i");
        b.className = "tball";
        b.style.fontSize = s[2] + "px";
        b.style.animationDuration = s[4] + "s";
        b.style.animationDelay = s[5] + "s";
        wrap.appendChild(b);
        layer.appendChild(wrap);
      });
      var ticking = false;
      window.addEventListener("scroll", function () {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(function () {
          layer.style.setProperty("--sy", window.pageYOffset);
          ticking = false;
        });
      }, { passive: true });
    }

    if (ctx) {
      resize();
      window.addEventListener("resize", resize);
    }

    if (!finePointer) return;

    $$(".card .inner").forEach(function (el) {
      el.addEventListener("pointermove", function (e) {
        var b = el.getBoundingClientRect();
        var x = (e.clientX - b.left) / b.width;
        var y = (e.clientY - b.top) / b.height;
        el.style.setProperty("--ry", ((x - 0.5) * 6).toFixed(2) + "deg");
        el.style.setProperty("--rx", ((0.5 - y) * 8).toFixed(2) + "deg");
        el.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
        el.style.setProperty("--my", (y * 100).toFixed(1) + "%");
      });
      el.addEventListener("pointerleave", function () {
        el.style.setProperty("--rx", "0deg");
        el.style.setProperty("--ry", "0deg");
      });
    });

    if (ctx) {
      var lx = -99;
      var ly = -99;
      window.addEventListener("pointermove", function (e) {
        if (e.pointerType !== "mouse") return;
        var dx = e.clientX - lx;
        var dy = e.clientY - ly;
        if (dx * dx + dy * dy < 64) return;
        lx = e.clientX;
        ly = e.clientY;
        if (parts.length < MAX_PARTS) parts.push({ t: "d", x: lx, y: ly, r: 5, life: 0.55, max: 0.55 });
        kick();
      }, { passive: true });
    }
  }

  /* ---------- intro splash ---------- */

  var splash = $("#splash");
  var started = false;
  var timer = null;

  function start() {
    if (started) return;
    started = true;
    clearTimeout(timer);
    document.removeEventListener("keydown", onKey);
    root.classList.add("ready");
    if (splash) {
      splash.classList.add("done");
      setTimeout(function () { splash.style.display = "none"; }, 800);
    }
    revealSections();
    ambient();
  }

  function onKey(e) {
    if (e.key === "Escape" || e.key === "Enter" || e.key === " ") start();
  }

  document.addEventListener("visibilitychange", function () {
    root.classList.toggle("paused", document.hidden);
  });

  if (reduce || !splash) {
    start();
  } else {
    splash.addEventListener("click", start);
    document.addEventListener("keydown", onKey);
    timer = setTimeout(start, 3000);
  }
})();
