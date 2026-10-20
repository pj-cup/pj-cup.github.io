(function () {
  "use strict";

  var root = document.documentElement;
  var supported = typeof HTMLDialogElement === "function" &&
    typeof HTMLDialogElement.prototype.showModal === "function";
  if (!supported) return; // the CSS :target fallback shows cards without this script

  root.classList.add("pc-js");

  var FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
  var current = null;
  var rendered = {}; // slug -> Promise<Blob|null>, so a share tap can stay synchronous

  function cardFor(hash) {
    if (!hash || hash.indexOf("#player-") !== 0) return null;
    var el = document.getElementById(decodeURIComponent(hash.slice(1)));
    return el && el.tagName === "DIALOG" ? el : null;
  }

  function setHash(hash) {
    try {
      history.replaceState(null, "", hash || location.pathname + location.search);
    } catch (e) {}
  }

  function open(dlg) {
    if (current && current !== dlg && current.open) current.close();
    if (!dlg.open) dlg.showModal();
    current = dlg;
    setHash("#" + dlg.id);
    prepareImage(dlg);
  }

  document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest("a.player-link");
    if (link) {
      var dlg = cardFor(link.getAttribute("href"));
      if (dlg) {
        e.preventDefault();
        open(dlg);
      }
      return;
    }
    var close = e.target.closest && e.target.closest(".pc-close");
    if (close && current) {
      e.preventDefault();
      current.close();
      return;
    }
    // A click on the dialog box itself (not its content) is a backdrop click.
    if (current && e.target === current) current.close();
  });

  Array.prototype.forEach.call(document.querySelectorAll("dialog.player-card"), function (dlg) {
    dlg.addEventListener("close", function () {
      if (current === dlg) {
        current = null;
        setHash("");
      }
    });
    var btn = dlg.querySelector(".pc-share");
    if (btn) {
      btn.hidden = false;
      btn.addEventListener("click", function () { share(dlg, btn); });
    }
  });

  /* ---------- share card as a PNG ---------- */

  var logo = new Promise(function (resolve) {
    var img = new Image();
    img.onload = function () { resolve(img); };
    img.onerror = function () { resolve(null); };
    img.src = "logo.png";
  });

  function prepareImage(dlg) {
    if (!rendered[dlg.id]) {
      var data = JSON.parse(dlg.getAttribute("data-share"));
      rendered[dlg.id] = logo.then(function (img) {
        return new Promise(function (resolve) {
          var canvas = drawCard(data, img);
          if (!canvas.toBlob) return resolve(null);
          canvas.toBlob(function (blob) { resolve(blob); }, "image/png");
        });
      }).catch(function () { return null; });
    }
    return rendered[dlg.id];
  }

  function download(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
  }

  function share(dlg, btn) {
    var data = JSON.parse(dlg.getAttribute("data-share"));
    var filename = "pj-cup-" + data.slug.replace(/^player-/, "") + ".png";
    btn.disabled = true;
    prepareImage(dlg).then(function (blob) {
      btn.disabled = false;
      if (!blob) return;
      var file = typeof File === "function" ? new File([blob], filename, { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({
          files: [file],
          title: data.name + " · " + data.site,
          text: data.name + " · " + data.site + " — https://" + data.url + "/#" + data.slug
        }).catch(function (err) {
          if (err && err.name !== "AbortError") download(blob, filename);
        });
      } else {
        download(blob, filename);
      }
    });
  }

  /* ---------- canvas drawing (fixed 1080x1350, always the dark card style) ---------- */

  var C = {
    bg1: "#15294a", bg2: "#0b1626", fg: "#f2f6fb", muted: "#9fb0c8",
    tile: "rgba(255,255,255,0.07)", line: "rgba(255,255,255,0.12)",
    area: "rgba(58,98,150,0.45)", grid: "rgba(160,190,230,0.55)",
    shapeFill: "rgba(200,230,60,0.55)", accent: "#e4f53b",
    up: "#34d27b", down: "#f0625f"
  };

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function text(ctx, str, x, y, size, color, weight, align) {
    ctx.font = (weight || "400") + " " + size + "px " + FONT;
    ctx.fillStyle = color;
    ctx.textAlign = align || "left";
    ctx.fillText(str, x, y);
  }

  function point(cx, cy, r, i) {
    var a = (-90 + 60 * i) * Math.PI / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  }

  function hexPath(ctx, cx, cy, r, values) {
    ctx.beginPath();
    for (var i = 0; i < 6; i++) {
      var p = point(cx, cy, r * (values ? values[i] / 10 : 1), i);
      if (i === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
    }
    ctx.closePath();
  }

  function drawCard(d, img) {
    var W = 1080, H = 1350;
    var canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext("2d");

    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, C.bg1);
    g.addColorStop(1, C.bg2);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    // header: logo, site, snapshot date
    if (img) {
      ctx.save();
      roundRect(ctx, 60, 56, 96, 96, 18);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.clip();
      ctx.drawImage(img, 64, 60, 88, 88);
      ctx.restore();
    }
    var hx = img ? 180 : 60;
    text(ctx, d.site.toUpperCase(), hx, 98, 34, C.fg, "800");
    text(ctx, "Snapshot " + d.date, hx, 138, 26, C.muted);

    // name, rank, record
    text(ctx, d.name, 60, 300, 110, C.fg, "800");
    ctx.font = "700 36px " + FONT;
    var rankStr = "RANK #" + d.rank;
    text(ctx, rankStr, 60, 362, 36, C.accent, "700");
    var x = 60 + ctx.measureText(rankStr).width + 18;
    if (d.move !== null && d.move !== undefined) {
      var mv = d.move > 0 ? "▲" + d.move : d.move < 0 ? "▼" + -d.move : "–";
      var mc = d.move > 0 ? C.up : d.move < 0 ? C.down : C.muted;
      text(ctx, mv, x, 362, 32, mc, "700");
      ctx.font = "700 32px " + FONT;
      x += ctx.measureText(mv).width + 18;
    }
    text(ctx, "·  " + d.record, x, 362, 34, C.muted, "600");

    // stat tiles: 2 rows of 4
    var tw = 225, th = 110, gap = 20;
    d.tiles.forEach(function (t, i) {
      var tx = 60 + (i % 4) * (tw + gap), ty = 400 + Math.floor(i / 4) * (th + gap);
      roundRect(ctx, tx, ty, tw, th, 16);
      ctx.fillStyle = C.tile;
      ctx.fill();
      text(ctx, t[0], tx + 20, ty + 38, 22, C.muted, "600");
      text(ctx, String(t[1]), tx + 20, ty + 92, 46, C.fg, "800");
    });

    // radar
    text(ctx, "PLAYER INSIGHTS", W / 2, 700, 40, C.fg, "800", "center");
    var cx = W / 2, cy = 1000, R = 160, LR = 196;
    hexPath(ctx, cx, cy, R);
    ctx.fillStyle = C.area;
    ctx.fill();
    ctx.strokeStyle = C.grid;
    ctx.lineWidth = 2;
    [0.25, 0.5, 0.75].forEach(function (f) {
      hexPath(ctx, cx, cy, R * f);
      ctx.globalAlpha = 0.35;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });
    for (var i = 0; i < 6; i++) {
      var p = point(cx, cy, R, i);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(p[0], p[1]);
      ctx.stroke();
    }
    ctx.setLineDash([10, 8]);
    hexPath(ctx, cx, cy, R);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = C.grid;
    for (i = 0; i < 6; i++) {
      p = point(cx, cy, R, i);
      ctx.beginPath();
      ctx.arc(p[0], p[1], 6, 0, Math.PI * 2);
      ctx.fill();
    }
    var values = d.axes.map(function (a) { return a[1] === null ? 0 : a[1]; });
    hexPath(ctx, cx, cy, R, values);
    ctx.fillStyle = C.shapeFill;
    ctx.fill();
    ctx.strokeStyle = C.accent;
    ctx.lineWidth = 7;
    ctx.lineJoin = "round";
    ctx.stroke();

    d.axes.forEach(function (a, i) {
      var p = point(cx, cy, LR, i), align, ly, vy;
      if (i === 0) { align = "center"; ly = p[1] - 52; vy = p[1]; }
      else if (i === 3) { align = "center"; ly = p[1] + 20; vy = p[1] + 72; }
      else { align = i < 3 ? "left" : "right"; ly = p[1] - 8; vy = p[1] + 46; }
      var top = i === d.top;
      text(ctx, a[0], p[0], ly, 26, top ? C.accent : C.fg, "700", align);
      text(ctx, a[1] === null ? "–" : a[1].toFixed(1), p[0], vy, 54, top ? C.accent : C.fg, "800", align);
    });

    // footer
    ctx.fillStyle = C.line;
    ctx.fillRect(60, 1288, W - 120, 2);
    text(ctx, d.url, 60, 1326, 26, C.muted, "600");
    text(ctx, "Season to date · scores out of 10", W - 60, 1326, 24, C.muted, "400", "right");

    return canvas;
  }

  /* ---------- deep links: #player-x opens that card (last, once everything is set up) ---------- */

  function fromHash() {
    var dlg = cardFor(location.hash);
    if (dlg) open(dlg);
  }
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
