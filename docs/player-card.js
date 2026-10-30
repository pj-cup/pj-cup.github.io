(function () {
  "use strict";

  var root = document.documentElement;
  var supported = typeof HTMLDialogElement === "function" &&
    typeof HTMLDialogElement.prototype.showModal === "function";
  if (!supported) return; // the CSS :target fallback shows cards without this script

  root.classList.add("pc-js");

  var FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, ' +
    'Thonburi, "Noto Sans Thai", "Leelawadee UI", sans-serif';

  // Runtime-only strings; the page's <html lang> (set by build.py) picks the language.
  // Stat labels and the W/D/L record come pre-translated in the compare-data / data-share JSON.
  var I18N = {
    en: {
      notPlayed: "Not played yet", inProgress: "In progress — not yet counted",
      won: function (name) { return name + " won"; }, draw: "Draw",
      vs: "VS", versus: " vs ", h2hCaps: "HEAD-TO-HEAD", insightsCaps: "PLAYER INSIGHTS",
      cmpNote: "Season to date · insights out of 10",
      snapshot: "Snapshot ", rankNo: "RANK #",
      setGame: function (set, game) { return "Set " + set + " · Game " + game; },
      set: "Set", replay: "Replay", skip: "Skip",
      illustrative: "Game order is illustrative — only set scores are recorded."
    },
    th: {
      notPlayed: "ยังไม่ได้แข่ง", inProgress: "กำลังแข่ง — ยังไม่นับคะแนน",
      won: function (name) { return name + " ชนะ"; }, draw: "เสมอ",
      vs: "VS", versus: " พบ ", h2hCaps: "ผลการพบกัน", insightsCaps: "ค่าพลังผู้เล่น",
      cmpNote: "ตลอดฤดูกาล · คะแนนเต็ม 10",
      snapshot: "ข้อมูล ณ ", rankNo: "อันดับ #",
      setGame: function (set, game) { return "เซต " + set + " · เกม " + game; },
      set: "เซต", replay: "ดูอีกครั้ง", skip: "ข้าม",
      illustrative: "ลำดับเกมเป็นภาพจำลอง — บันทึกไว้เฉพาะสกอร์ของแต่ละเซต"
    }
  };
  var L = I18N[root.lang] || I18N.en;
  var current = null;
  var rendered = {}; // key -> Promise<Blob|null>, so a share tap can stay synchronous
  var cmpDlg = document.getElementById("compare");
  var cmpData = null;
  try {
    cmpData = JSON.parse(document.getElementById("compare-data").textContent);
  } catch (e) {}
  var LBL = (cmpData && cmpData.labels) || {};
  var matchDlg = document.getElementById("match");

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

  function show(dlg, hash) {
    if (current && current !== dlg && current.open) current.close();
    if (!dlg.open) dlg.showModal();
    current = dlg;
    setHash(hash);
  }

  function open(dlg) {
    show(dlg, "#" + dlg.id);
    prepareCard(dlg);
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
    var match = e.target.closest && e.target.closest("a.match-link");
    if (match) {
      var keys = matchFor(match.getAttribute("href"));
      if (keys) {
        e.preventDefault();
        openMatch(keys[0], keys[1]);
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

  // The modal makes the header's TH/EN switch inert, so each dialog gets its own copy;
  // theme.js appends the open #player-x / #compare-a-vs-b hash when it's clicked.
  var langToggle = document.querySelector(".site-header .lang-toggle");

  Array.prototype.forEach.call(document.querySelectorAll("dialog.player-card"), function (dlg) {
    var closeBtn = dlg.querySelector(".pc-close");
    if (langToggle && closeBtn) closeBtn.parentNode.insertBefore(langToggle.cloneNode(true), closeBtn);
    dlg.addEventListener("close", function () {
      if (current === dlg) {
        current = null;
        setHash("");
      }
    });
    if (dlg === cmpDlg || dlg === matchDlg) return;
    var btn = dlg.querySelector(".pc-share");
    if (btn) {
      btn.hidden = false;
      btn.addEventListener("click", function () { shareCard(dlg, btn); });
    }
    var picker = dlg.querySelector(".pc-compare");
    if (picker && cmpDlg && cmpData) {
      picker.hidden = false;
      var select = picker.querySelector("select");
      select.addEventListener("change", function () {
        var other = select.value;
        select.value = "";
        if (other) openCompare(dlg.id.replace(/^player-/, ""), other);
      });
    }
  });

  if (cmpDlg && cmpData) {
    var cmpBtn = cmpDlg.querySelector(".pc-share");
    cmpBtn.hidden = false;
    cmpBtn.addEventListener("click", function () { shareCompare(cmpBtn); });
  }

  /* ---------- compare two players ---------- */

  function esc(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function ratio(won, lost) {
    return won + lost ? won / (won + lost) : null;
  }

  function signed(n) {
    return n === null ? "–" : n > 0 ? "+" + n : n < 0 ? "−" + -n : "0";
  }

  // [label, display(p), score(p) for "better" (null = no data), direction: 1 higher wins, -1 lower wins, 0 not compared]
  var ROWS = [
    [LBL.rank, function (p) { return "#" + p.rank; }, function (p) { return parseInt(p.rank, 10); }, -1],
    [LBL.mp, function (p) { return p.mp; }, null, 0],
    [LBL.wdl, function (p) { return p.w + "–" + p.d + "–" + p.l; }, null, 0],
    [LBL.pts, function (p) { return p.pts; }, function (p) { return p.pts; }, 1],
    [LBL.ppm, function (p) { return p.ppm; }, function (p) { return p.mp ? p.pts / p.mp : null; }, 1],
    [LBL.sets, function (p) { return p.sets_w + "–" + p.sets_l; }, function (p) { return ratio(p.sets_w, p.sets_l); }, 1],
    [LBL.close, function (p) { return p.close_w + p.close_l ? p.close_w + "–" + p.close_l : "–"; }, function (p) { return ratio(p.close_w, p.close_l); }, 1],
    [LBL.gf, function (p) { return p.gf; }, function (p) { return p.gf; }, 1],
    [LBL.ga, function (p) { return p.ga; }, function (p) { return p.mp ? p.ga : null; }, -1], // 0 conceded in 0 matches is no merit
    [LBL.gd, function (p) { return signed(p.gd); }, function (p) { return p.gd; }, 1]
  ];

  // Rows with the winning side: "a", "b" or "" (tie, no data, or not compared).
  function compareRows(a, b) {
    return ROWS.map(function (r) {
      var better = "";
      if (r[2] && r[3]) {
        var sa = r[2](a), sb = r[2](b);
        if (sa !== null && sb !== null && !isNaN(sa) && !isNaN(sb) && sa !== sb) {
          better = (sa - sb) * r[3] > 0 ? "a" : "b";
        }
      }
      var va = r[1](a), vb = r[1](b);
      return [r[0], va === null ? "–" : String(va), vb === null ? "–" : String(vb), better];
    });
  }

  // Their meeting, from A's perspective; both mirrored cells kept as-is.
  function headToHead(ka, kb) {
    var ab = (cmpData.h2h[ka] || {})[kb] || null;
    var ba = (cmpData.h2h[kb] || {})[ka] || null;
    var cell = ab || ba;
    var flip = { win: "loss", loss: "win", draw: "draw" };
    return {
      ab: ab ? ab[1] : "",
      ba: ba ? ba[1] : "",
      state: cell ? cell[0] : "none",
      outcome: ab ? ab[2] : ba ? flip[ba[2]] || "" : ""
    };
  }

  function h2hSummary(a, b, h) {
    if (h.state === "none") return L.notPlayed;
    if (h.state === "ongoing") return L.inProgress;
    if (h.outcome === "win") return L.won(a.name);
    if (h.outcome === "loss") return L.won(b.name);
    return L.draw;
  }

  function moveHtml(move) {
    if (move === null || move === undefined) return "";
    var cls = move > 0 ? "up" : move < 0 ? "down" : "same";
    var txt = move > 0 ? "▲" + move : move < 0 ? "▼" + -move : "–";
    return ' <span class="rank-move ' + cls + '">' + txt + "</span>";
  }

  function compareRadar(a, b) {
    var cx = 190, cy = 180, r = 95, lr = 114;
    function pt(radius, i) { return point(cx, cy, radius, i); }
    function ring(frac) {
      var out = [];
      for (var i = 0; i < 6; i++) out.push(pt(r * frac, i).map(function (n) { return n.toFixed(1); }).join(","));
      return out.join(" ");
    }
    function shape(p) {
      return p.axes.map(function (ax, i) {
        return pt(r * (ax[1] || 0) / 10, i).map(function (n) { return n.toFixed(1); }).join(",");
      }).join(" ");
    }
    function fmt(v) { return v === null ? "–" : v.toFixed(1); }
    var label = cmpData.axes.map(function (ax, i) {
      return ax.charAt(0) + ax.slice(1).toLowerCase() + " " + fmt(a.axes[i][1]) + L.versus + fmt(b.axes[i][1]);
    }).join(", ");
    var parts = ['<svg class="radar" viewBox="0 0 380 360" role="img" aria-label="' + esc(label) + '">',
      '<polygon class="rg-area" points="' + ring(1) + '"/>'];
    [0.25, 0.5, 0.75].forEach(function (f) { parts.push('<polygon class="rg-ring" points="' + ring(f) + '"/>'); });
    for (var i = 0; i < 6; i++) {
      var p = pt(r, i);
      parts.push('<line class="rg-spoke" x1="' + cx + '" y1="' + cy + '" x2="' + p[0].toFixed(1) + '" y2="' + p[1].toFixed(1) + '"/>');
    }
    parts.push('<polygon class="rg-outer" points="' + ring(1) + '"/>');
    parts.push('<polygon class="rg-shape a" points="' + shape(a) + '"/>');
    parts.push('<polygon class="rg-shape b" points="' + shape(b) + '"/>');
    cmpData.axes.forEach(function (ax, i) {
      var p = pt(lr, i), anchor, ly, vy;
      if (i === 0) { anchor = "middle"; ly = p[1] - 30; vy = p[1] - 4; }
      else if (i === 3) { anchor = "middle"; ly = p[1] + 10; vy = p[1] + 34; }
      else { anchor = i < 3 ? "start" : "end"; ly = p[1] - 6; vy = p[1] + 18; }
      parts.push(
        '<text class="rg-label" x="' + p[0].toFixed(1) + '" y="' + ly.toFixed(1) + '" text-anchor="' + anchor + '">' + ax + "</text>" +
        '<text class="rg-value cmp" x="' + p[0].toFixed(1) + '" y="' + vy.toFixed(1) + '" text-anchor="' + anchor + '">' +
        '<tspan class="a">' + fmt(a.axes[i][1]) + '</tspan><tspan class="sep"> · </tspan><tspan class="b">' + fmt(b.axes[i][1]) + "</tspan></text>"
      );
    });
    parts.push("</svg>");
    return parts.join("");
  }

  function compareSide(p, side) {
    return '<div class="cmp-side ' + side + '"><span class="pc-rank">' + esc(p.rank) + "</span>" +
      '<a class="player-link" href="#player-' + esc(p.key) + '">' + esc(p.name) + "</a>" +
      '<p class="pc-record">' + esc(p.record) + moveHtml(p.move) + "</p></div>";
  }

  function renderCompare(a, b) {
    var h = headToHead(a.key, b.key);
    var cells = h.state === "none" ? "" :
      '<ul class="pc-results">' +
      [[a, h.ab], [b, h.ba]].map(function (c) {
        return '<li><span class="opp">' + esc(c[0].name) + '</span><span class="score">' + (c[1] ? esc(c[1]) : "–") + "</span></li>";
      }).join("") + "</ul>";
    var chip = h.state === "result"
      ? '<span class="chip ' + h.outcome + '">' + (cmpData.letters[h.outcome] || "?") + "</span>"
      : h.state === "ongoing" ? '<span class="chip live">•</span>' : "";
    var rows = compareRows(a, b).map(function (r) {
      return '<div class="cmp-row"><b class="a' + (r[3] === "a" ? " better" : "") + '">' + esc(r[1]) + "</b>" +
        "<span>" + esc(r[0]) + "</span>" +
        '<b class="b' + (r[3] === "b" ? " better" : "") + '">' + esc(r[2]) + "</b></div>";
    }).join("");
    return '<div class="cmp-head">' + compareSide(a, "a") + '<span class="cmp-vs">' + L.vs + '</span>' + compareSide(b, "b") + "</div>" +
      '<div class="pc-block"><h4>' + esc(LBL.h2h) + '</h4><p class="cmp-h2h">' + chip + "<span>" + esc(h2hSummary(a, b, h)) + "</span></p>" + cells + "</div>" +
      '<div class="pc-block cmp-rows">' + rows + "</div>" +
      '<div class="pc-block pc-insights"><h4>' + esc(LBL.insights) + '</h4><p class="pc-sub">' + esc(LBL.sub) + "</p>" +
      compareRadar(a, b) + "</div>";
  }

  function comparePlayers(ka, kb) {
    var a = cmpData.players[ka], b = cmpData.players[kb];
    if (!a || !b || ka === kb) return null;
    a.key = ka;
    b.key = kb;
    return [a, b];
  }

  function openCompare(ka, kb) {
    var pair = comparePlayers(ka, kb);
    if (!pair) return;
    cmpDlg.querySelector(".cmp-title").textContent = pair[0].name + L.versus + pair[1].name;
    cmpDlg.querySelector(".cmp-body").innerHTML = renderCompare(pair[0], pair[1]);
    cmpDlg.setAttribute("data-pair", ka + "-vs-" + kb);
    show(cmpDlg, "#compare-" + ka + "-vs-" + kb);
    cmpDlg.scrollTop = 0;
    prepareCompare(ka, kb);
  }

  // "#<prefix><a>-vs-<b>": match against known keys so a name containing "-vs-" can't mis-split.
  function pairFor(prefix, hash, ok) {
    if (!cmpData || !hash || hash.indexOf(prefix) !== 0) return null;
    var rest = decodeURIComponent(hash.slice(prefix.length));
    for (var ka in cmpData.players) {
      if (rest.indexOf(ka + "-vs-") === 0) {
        var kb = rest.slice(ka.length + 4);
        if (ok(ka, kb)) return [ka, kb];
      }
    }
    return null;
  }

  function compareFor(hash) {
    return cmpDlg ? pairFor("#compare-", hash, comparePlayers) : null;
  }

  /* ---------- match replay: a mini court rally, game by game, ending on the CSV score ---------- */

  // Only the row player's cell (its own perspective) opens a replay, exactly as clicked.
  function matchCell(ka, kb) {
    return comparePlayers(ka, kb) && (cmpData.h2h[ka] || {})[kb] || null;
  }

  function matchFor(hash) {
    return matchDlg ? pairFor("#match-", hash, matchCell) : null;
  }

  function seeded(str) {
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
    return function () { // mulberry32
      h = (h + 0x6d2b79f5) | 0;
      var x = Math.imul(h ^ (h >>> 15), 1 | h);
      x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
      return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Per set, a shuffled list of game winners ("a"/"b") that closes on the set winner.
  function gameOrder(sets, rand) {
    return sets.map(function (set) {
      var games = [], i;
      for (i = 0; i < set[0]; i++) games.push("a");
      for (i = 0; i < set[1]; i++) games.push("b");
      for (i = games.length - 1; i > 0; i--) {
        var j = Math.floor(rand() * (i + 1)), tmp = games[i];
        games[i] = games[j];
        games[j] = tmp;
      }
      if (set[0] !== set[1]) {
        var w = set[0] > set[1] ? "a" : "b";
        games.push(games.splice(games.lastIndexOf(w), 1)[0]);
      }
      return games;
    });
  }

  var CT = { x0: 24, x1: 296, y0: 22, y1: 138 }; // court box in the 320×160 viewBox
  var matchRun = 0; // bumped to cancel a running replay

  function matchCourt() {
    var mx = (CT.x0 + CT.x1) / 2, my = (CT.y0 + CT.y1) / 2, alley = 14;
    function line(x1, y1, x2, y2, cls) {
      return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '"' + (cls ? ' class="' + cls + '"' : "") + "/>";
    }
    return '<svg class="mt-court" viewBox="0 0 320 160" aria-hidden="true">' +
      '<rect class="mt-surface" x="4" y="4" width="312" height="152" rx="10"/>' +
      '<g class="mt-lines"><rect x="' + CT.x0 + '" y="' + CT.y0 + '" width="' + (CT.x1 - CT.x0) + '" height="' + (CT.y1 - CT.y0) + '"/>' +
      line(CT.x0, CT.y0 + alley, CT.x1, CT.y0 + alley) + line(CT.x0, CT.y1 - alley, CT.x1, CT.y1 - alley) +
      line(mx - 70, CT.y0 + alley, mx - 70, CT.y1 - alley) + line(mx + 70, CT.y0 + alley, mx + 70, CT.y1 - alley) +
      line(mx - 70, my, mx + 70, my) + "</g>" +
      line(mx, CT.y0 - 8, mx, CT.y1 + 8, "mt-net") +
      '<ellipse class="mt-shadow" rx="4" ry="2" cx="-20" cy="-20"/>' +
      '<circle class="mt-p a" r="7" cx="' + (CT.x0 + 6) + '" cy="' + my + '"/>' +
      '<circle class="mt-p b" r="7" cx="' + (CT.x1 - 6) + '" cy="' + my + '"/>' +
      '<circle class="mt-ball" r="3.6" cx="-20" cy="-20"/>' +
      "</svg>";
  }

  function openMatch(ka, kb) {
    var cell = matchCell(ka, kb);
    if (!cell) return;
    var a = cmpData.players[ka], b = cmpData.players[kb];
    var sets = [], m, re = /(\d+)\s*-\s*(\d+)/g;
    while ((m = re.exec(cell[1]))) sets.push([parseInt(m[1], 10), parseInt(m[2], 10)]);
    var head = sets.map(function (_, i) { return "<th>" + esc(L.set) + " " + (i + 1) + "</th>"; }).join("");
    function row(p, side) {
      return '<tr class="' + side + '"><th><i></i>' + esc(p.name) + "</th>" +
        sets.map(function (_, i) { return '<td data-set="' + i + '">0</td>'; }).join("") + "</tr>";
    }
    matchDlg.querySelector(".cmp-title").textContent = a.name + L.versus + b.name;
    matchDlg.querySelector(".mt-body").innerHTML =
      '<p class="mt-raw">' + esc(cell[1]) + "</p>" + matchCourt() +
      '<table class="mt-score"><thead><tr><th></th>' + head + "</tr></thead><tbody>" +
      row(a, "a") + row(b, "b") + "</tbody></table>" +
      '<p class="mt-status" aria-live="polite"></p>' +
      '<p class="pc-sub mt-note">' + esc(L.illustrative) + "</p>" +
      '<div class="pc-actions mt-actions"><button class="pc-share mt-skip" type="button">' + esc(L.skip) + "</button>" +
      '<button class="pc-share mt-replay" type="button" hidden>' + esc(L.replay) + "</button></div>";
    var final = cell[0] === "ongoing" ? L.inProgress :
      cell[2] === "win" ? L.won(a.name) : cell[2] === "loss" ? L.won(b.name) : L.draw;
    var body = matchDlg.querySelector(".mt-body");
    var done = cell[0] === "result"; // an in-progress set has no winner yet
    var start = function () { playMatch(body, sets, gameOrder(sets, seeded(ka + "|" + kb + "|" + cell[1])), final, done); };
    body.querySelector(".mt-replay").addEventListener("click", start);
    body.querySelector(".mt-skip").addEventListener("click", function () {
      matchRun++;
      finishMatch(body, sets, final, done);
    });
    show(matchDlg, "#match-" + ka + "-vs-" + kb);
    matchDlg.scrollTop = 0;
    start();
  }

  function finishMatch(body, sets, final, done) {
    sets.forEach(function (set, i) { setScore(body, i, set[0], set[1], done); });
    var ball = body.querySelector(".mt-ball"), shadow = body.querySelector(".mt-shadow");
    ball.setAttribute("cx", -20);
    shadow.setAttribute("cx", -20);
    body.querySelector(".mt-status").textContent = final;
    body.querySelector(".mt-skip").hidden = true;
    body.querySelector(".mt-replay").hidden = false;
  }

  function setScore(body, i, ga, gb, done) {
    var tds = body.querySelectorAll('.mt-score td[data-set="' + i + '"]');
    tds[0].textContent = ga;
    tds[1].textContent = gb;
    tds[0].classList.toggle("won", !!done && ga > gb);
    tds[1].classList.toggle("won", !!done && gb > ga);
  }

  function playMatch(body, sets, order, final, done) {
    var run = ++matchRun;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    body.querySelector(".mt-skip").hidden = false;
    body.querySelector(".mt-replay").hidden = true;
    sets.forEach(function (_, i) { setScore(body, i, 0, 0, false); });
    if (reduce || !window.requestAnimationFrame) return finishMatch(body, sets, final, done);

    var rand = seeded(order.join());
    var ball = body.querySelector(".mt-ball"), shadow = body.querySelector(".mt-shadow");
    var pl = { a: body.querySelector(".mt-p.a"), b: body.querySelector(".mt-p.b") };
    var hitX = { a: CT.x0 + 6, b: CT.x1 - 6 };
    var pos = { a: (CT.y0 + CT.y1) / 2, b: (CT.y0 + CT.y1) / 2 };
    pl.a.setAttribute("cy", pos.a);
    pl.b.setAttribute("cy", pos.b);
    var status = body.querySelector(".mt-status");
    var total = order.reduce(function (n, g) { return n + g.length; }, 0);
    var gameMs = Math.max(450, Math.min(1100, 7000 / Math.max(total, 1)));

    // Flatten into shots: winner hits last, the final shot runs past the loser's baseline.
    var steps = [];
    order.forEach(function (games, si) {
      var score = [0, 0];
      games.forEach(function (w, gi) {
        var shots = 2 + Math.floor(rand() * 3), other = w === "a" ? "b" : "a";
        var hitter = shots % 2 ? w : other, y = pos[hitter];
        for (var k = 0; k < shots; k++) {
          var last = k === shots - 1, to = hitter === "a" ? "b" : "a";
          var ty = CT.y0 + 10 + rand() * (CT.y1 - CT.y0 - 20);
          steps.push({
            set: si, game: gi, from: hitter, to: to, y0: y, y1: ty, last: last,
            ms: gameMs * 0.8 / shots
          });
          hitter = to;
          y = ty;
        }
        score[w === "a" ? 0 : 1]++;
        steps.push({ set: si, game: gi, pause: true, ms: gameMs * 0.2, score: score.slice(), w: w,
          done: done && gi === games.length - 1 });
      });
    });

    var idx = 0, t0 = null;
    function frame(ts) {
      if (run !== matchRun || !matchDlg.open) return;
      if (t0 === null) t0 = ts;
      var st = steps[idx];
      if (!st) return finishMatch(body, sets, final, done);
      var p = Math.min(1, (ts - t0) / st.ms);
      if (st.pause) {
        if (p >= 1) {
          setScore(body, st.set, st.score[0], st.score[1], st.done);
          var td = body.querySelectorAll('.mt-score td[data-set="' + st.set + '"]')[st.w === "a" ? 0 : 1];
          td.classList.remove("pulse");
          void td.offsetWidth; // restart the pulse
          td.classList.add("pulse");
        }
      } else {
        status.textContent = L.setGame(st.set + 1, st.game + 1);
        // The winning shot carries on past the receiver.
        var x1 = st.last ? (st.to === "a" ? 2 : 318) : hitX[st.to];
        var x = hitX[st.from] + (x1 - hitX[st.from]) * p;
        var y = st.y0 + (st.y1 - st.y0) * p;
        var lift = Math.sin(Math.PI * Math.min(p * 1.15, 1)) * 16; // bounce just before arrival
        ball.setAttribute("cx", x.toFixed(1));
        ball.setAttribute("cy", (y - lift).toFixed(1));
        shadow.setAttribute("cx", x.toFixed(1));
        shadow.setAttribute("cy", (y + 4).toFixed(1));
        // The receiver chases the ball; on the winning shot they only get partway.
        var reach = st.last ? 0.45 : 1;
        var py = pos[st.to] + (st.y1 - pos[st.to]) * Math.min(1, p * 1.3) * reach;
        pl[st.to].setAttribute("cy", py.toFixed(1));
        if (p >= 1) pos[st.to] = py;
      }
      if (p >= 1) {
        idx++;
        t0 = ts;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------- share card as a PNG ---------- */

  var logo = new Promise(function (resolve) {
    var img = new Image();
    img.onload = function () { resolve(img); };
    img.onerror = function () { resolve(null); };
    img.src = "logo.png";
  });

  function prepareImage(key, draw) {
    if (!rendered[key]) {
      rendered[key] = logo.then(function (img) {
        return new Promise(function (resolve) {
          var canvas = draw(img);
          if (!canvas.toBlob) return resolve(null);
          canvas.toBlob(function (blob) { resolve(blob); }, "image/png");
        });
      }).catch(function () { return null; });
    }
    return rendered[key];
  }

  function prepareCard(dlg) {
    var data = JSON.parse(dlg.getAttribute("data-share"));
    return prepareImage(dlg.id, function (img) { return drawCard(data, img); });
  }

  function prepareCompare(ka, kb) {
    var pair = comparePlayers(ka, kb);
    return prepareImage("compare-" + ka + "-vs-" + kb, function (img) {
      return drawCompare(pair[0], pair[1], img);
    });
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

  function shareCard(dlg, btn) {
    var data = JSON.parse(dlg.getAttribute("data-share"));
    share(prepareCard(dlg), btn, "pj-cup-" + data.slug.replace(/^player-/, "") + ".png",
      data.name + " · " + data.site, data.page + "#" + data.slug);
  }

  function shareCompare(btn) {
    var pair = cmpDlg.getAttribute("data-pair");
    var keys = compareFor("#compare-" + pair);
    if (!keys) return;
    var players = comparePlayers(keys[0], keys[1]);
    share(prepareCompare(keys[0], keys[1]), btn, "pj-cup-" + pair + ".png",
      players[0].name + L.versus + players[1].name + " · " + cmpData.site,
      cmpData.page + "#compare-" + pair);
  }

  function share(image, btn, filename, title, link) {
    btn.disabled = true;
    image.then(function (blob) {
      btn.disabled = false;
      if (!blob) return;
      var file = typeof File === "function" ? new File([blob], filename, { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({
          files: [file],
          title: title,
          text: title + " — " + link
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
    up: "#34d27b", down: "#f0625f",
    shapeFillA: "rgba(200,230,60,0.35)", b: "#4cc9f0", shapeFillB: "rgba(76,201,240,0.35)",
    win: "#34d27b", draw: "#f0b429", loss: "#f0625f"
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

  var W = 1080, H = 1350;

  // Background, header (logo, site, snapshot date) and footer shared by both share images.
  function drawFrame(img, site, date, url, note) {
    var canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext("2d");

    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, C.bg1);
    g.addColorStop(1, C.bg2);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

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
    text(ctx, site.toUpperCase(), hx, 98, 34, C.fg, "800");
    text(ctx, L.snapshot + date, hx, 138, 26, C.muted);

    ctx.fillStyle = C.line;
    ctx.fillRect(60, 1288, W - 120, 2);
    text(ctx, url, 60, 1326, 26, C.muted, "600");
    text(ctx, note, W - 60, 1326, 24, C.muted, "400", "right");
    return { canvas: canvas, ctx: ctx };
  }

  // Hexagon grid (area, rings, spokes, dashed outline, corner dots).
  function drawRadarGrid(ctx, cx, cy, R) {
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
  }

  function drawShape(ctx, cx, cy, R, axes, fill, stroke, width) {
    hexPath(ctx, cx, cy, R, axes.map(function (a) { return a[1] === null ? 0 : a[1]; }));
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.lineJoin = "round";
    ctx.stroke();
  }

  // Largest font size (down to min) at which str fits in maxWidth.
  function fitSize(ctx, str, size, min, maxWidth, weight) {
    for (; size > min; size -= 4) {
      ctx.font = weight + " " + size + "px " + FONT;
      if (ctx.measureText(str).width <= maxWidth) break;
    }
    return size;
  }

  function drawCard(d, img) {
    var frame = drawFrame(img, d.site, d.date, d.url, d.sub);
    var canvas = frame.canvas, ctx = frame.ctx;

    // name, rank, record
    text(ctx, d.name, 60, 300, 110, C.fg, "800");
    ctx.font = "700 36px " + FONT;
    var rankStr = L.rankNo + d.rank;
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
    text(ctx, L.insightsCaps, W / 2, 700, 40, C.fg, "800", "center");
    var cx = W / 2, cy = 1000, R = 160, LR = 196;
    drawRadarGrid(ctx, cx, cy, R);
    drawShape(ctx, cx, cy, R, d.axes, C.shapeFill, C.accent, 7);

    d.axes.forEach(function (a, i) {
      var p = point(cx, cy, LR, i), align, ly, vy;
      if (i === 0) { align = "center"; ly = p[1] - 52; vy = p[1]; }
      else if (i === 3) { align = "center"; ly = p[1] + 20; vy = p[1] + 72; }
      else { align = i < 3 ? "left" : "right"; ly = p[1] - 8; vy = p[1] + 46; }
      var top = i === d.top;
      text(ctx, a[0], p[0], ly, 26, top ? C.accent : C.fg, "700", align);
      text(ctx, a[1] === null ? "–" : a[1].toFixed(1), p[0], vy, 54, top ? C.accent : C.fg, "800", align);
    });

    return canvas;
  }

  function drawCompare(a, b, img) {
    var frame = drawFrame(img, cmpData.site, cmpData.date, cmpData.url, L.cmpNote);
    var canvas = frame.canvas, ctx = frame.ctx;

    // names, ranks, records
    var size = Math.min(fitSize(ctx, a.name, 84, 40, 420, "800"), fitSize(ctx, b.name, 84, 40, 420, "800"));
    text(ctx, a.name, 60, 270, size, C.accent, "800");
    text(ctx, b.name, W - 60, 270, size, C.b, "800", "right");
    text(ctx, L.vs, W / 2, 262, 36, C.muted, "800", "center");
    text(ctx, L.rankNo + a.rank + "  ·  " + a.record, 60, 322, 28, C.muted, "700");
    text(ctx, L.rankNo + b.rank + "  ·  " + b.record, W - 60, 322, 28, C.muted, "700", "right");

    // head-to-head
    var h = headToHead(a.key, b.key);
    roundRect(ctx, 60, 348, W - 120, 76, 16);
    ctx.fillStyle = C.tile;
    ctx.fill();
    text(ctx, L.h2hCaps, 90, 395, 24, C.muted, "700");
    var hc = h.state === "result" ? C[h.outcome] || C.fg : h.state === "ongoing" ? C.draw : C.muted;
    var summary = h2hSummary(a, b, h) + (h.ab ? "  ·  " + h.ab : h.ba ? "  ·  " + h.ba : "");
    text(ctx, summary, W - 90, 397, fitSize(ctx, summary, 34, 22, 640, "800"), hc, "800", "right");

    // overlaid radar
    var cx = W / 2, cy = 676, R = 135, LR = 168;
    drawRadarGrid(ctx, cx, cy, R);
    drawShape(ctx, cx, cy, R, a.axes, C.shapeFillA, C.accent, 6);
    drawShape(ctx, cx, cy, R, b.axes, C.shapeFillB, C.b, 6);
    cmpData.axes.forEach(function (ax, i) {
      var p = point(cx, cy, LR, i), align, ly, vy;
      if (i === 0) { align = "center"; ly = p[1] - 46; vy = p[1] - 6; }
      else if (i === 3) { align = "center"; ly = p[1] + 26; vy = p[1] + 64; }
      else { align = i < 3 ? "left" : "right"; ly = p[1] - 8; vy = p[1] + 34; }
      text(ctx, ax, p[0], ly, 22, C.fg, "700", align);
      var va = a.axes[i][1] === null ? "–" : a.axes[i][1].toFixed(1);
      var vb = b.axes[i][1] === null ? "–" : b.axes[i][1].toFixed(1);
      ctx.font = "800 34px " + FONT;
      var wa = ctx.measureText(va).width, ws = ctx.measureText(" · ").width, wb = ctx.measureText(vb).width;
      var x0 = align === "left" ? p[0] : align === "right" ? p[0] - wa - ws - wb : p[0] - (wa + ws + wb) / 2;
      text(ctx, va, x0, vy, 34, C.accent, "800");
      text(ctx, " · ", x0 + wa, vy, 34, C.muted, "800");
      text(ctx, vb, x0 + wa + ws, vy, 34, C.b, "800");
    });

    // stat rows
    compareRows(a, b).forEach(function (r, i) {
      var y = 955 + i * 32;
      if (i % 2 === 0) {
        ctx.fillStyle = C.tile;
        ctx.fillRect(60, y - 24, W - 120, 32);
      }
      text(ctx, r[0], W / 2, y, 22, C.muted, "700", "center");
      text(ctx, r[1], 300, y, 28, r[3] === "a" ? C.accent : C.fg, r[3] === "a" ? "800" : "600", "center");
      text(ctx, r[2], W - 300, y, 28, r[3] === "b" ? C.b : C.fg, r[3] === "b" ? "800" : "600", "center");
    });

    return canvas;
  }

  /* ---------- deep links: #player-x / #compare-a-vs-b / #match-a-vs-b (last, once everything is set up) ---------- */

  function fromHash() {
    var match = matchFor(location.hash);
    if (match) return openMatch(match[0], match[1]);
    var pair = compareFor(location.hash);
    if (pair) return openCompare(pair[0], pair[1]);
    var dlg = cardFor(location.hash);
    if (dlg) open(dlg);
  }
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
