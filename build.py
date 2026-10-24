#!/usr/bin/env python3
"""Generate docs/ (GitHub Pages site) from the latest dated CSV snapshot in csv/."""

import csv
import html
import json
import math
import re
import shutil
import sys
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent
CSV_DIR = ROOT / "csv"
DOCS_DIR = ROOT / "docs"
TEMPLATE_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"
LOGO_SOURCE = ASSETS_DIR / "logo_1000.png"
SNAPSHOT_RE = re.compile(r"^\d{8}\.csv$")

STANDINGS_COLUMNS = [
    ("rank", False),
    ("name", False),
    ("mp", True),
    ("w", True),
    ("d", True),
    ("l", True),
    ("gf", True),
    ("ga", True),
    ("gd", True),
    ("pts", True),
    ("ppm", True),
    ("left", True),
    ("max", True),
]

# One pre-rendered page per language. English strings are the original literals;
# every key must exist in both languages. Runtime strings live in player-card.js (I18N).
LANGS = {
    "th": {"index": "index.html", "beta": "beta.html", "locale": "th_TH", "label": "ไทย"},
    "en": {"index": "en.html", "beta": "beta-en.html", "locale": "en_US", "label": "EN"},
}

# Plain text only (no markup or entities): escape with te() when it goes into HTML.
TEXT = {
    "en": {
        "col_rank": "#", "col_name": "Player", "col_mp": "MP", "col_w": "W", "col_d": "D",
        "col_l": "L", "col_gf": "GF", "col_ga": "GA", "col_gd": "GD", "col_pts": "Pts",
        "col_ppm": "Pts/MP", "col_left": "Left", "col_max": "Max",
        "tip_mp": "", "tip_w": "", "tip_d": "", "tip_l": "", "tip_gf": "", "tip_ga": "",
        "tip_gd": "", "tip_pts": "", "tip_ppm": "",
        "tip_left": "Opponents not yet played",
        "tip_max": "Most points still reachable if every remaining match is played",
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "year_offset": 0,
        "tba_text": "TBA",
        "tba_title": "Not played yet — planned to play",
        "ongoing_title": "Match in progress — not yet counted in standings",
        "places_1": "{n} place", "places_n": "{n} places",
        "move_up": "Up {places} since {date}",
        "move_down": "Down {places} since {date}",
        "move_same": "Same rank as {date}",
        "rules": "Rules",
        "description": "Tennis league standings and head-to-head results, updated {date}.",
        "standings": "Standings",
        "h2h": "Head-to-Head",
        "snapshot": "Snapshot: {date}",
        "source": "Source: {file}",
        "rank_change_vs": "Rank change vs {date}",
        "theme_toggle": "Toggle dark mode",
        "lang_toggle": "Language",
        "axis_ATTACK": "ATTACK", "axis_DOMINANCE": "DOMINANCE", "axis_FORM": "FORM",
        "axis_DEFENSE": "DEFENSE", "axis_CLUTCH": "CLUTCH", "axis_MOVEMENT": "MOVEMENT",
        "radar_label": "Player insights: {scores}",
        "compare_with": "Compare with",
        "choose_player": "Choose player…",
        "tile_mp": "MP", "tile_pts": "PTS", "tile_ppm": "PTS/MP", "tile_sets": "SETS W–L",
        "tile_close": "CLOSE", "tile_gf": "GF", "tile_ga": "GA", "tile_gd": "GD",
        "tile_rank": "RANK", "wdl": "W–D–L",
        "w": "W", "d": "D", "l": "L",
        "record": "{w}W{sep}{d}D{sep}{l}L",
        "since": "Since {date}",
        "in_progress": "in progress",
        "no_matches": "No matches played yet.",
        "close": "Close",
        "player_insights": "Player Insights",
        "insights_sub": "Season to date · scores out of 10",
        "results": "Results",
        "share_card": "Share card image",
        "compare": "Compare",
        "share_compare": "Share compare image",
        "tap_to_skip": "TAP TO SKIP",
        "classic_view": "Classic view",
        "mp_count": "{n} MP",
        "wins": "Wins", "draws": "Draws", "losses": "Losses",
        "games_bar": "Games for {gf}, against {ga}",
        "game_diff": "Game difference",
        "pts_small": "PTS",
        "ppm_suffix": "{ppm}/MP",
        "ppm_title": "Points per match played",
        "beta_suffix": "Beta",
        "progress": "{done} / {total} matches played ({pct}%)",
        "still_to_play": "Still to play",
        "max_possible": "Max possible: {n} pts if every remaining match is played",
        "all_played": "Every opponent played.",
        "left_max": "{left} left · max {max}",
    },
    "th": {
        "col_rank": "#", "col_name": "ผู้เล่น", "col_mp": "แข่ง", "col_w": "ชนะ", "col_d": "เสมอ",
        "col_l": "แพ้", "col_gf": "ได้", "col_ga": "เสีย", "col_gd": "ผลต่าง", "col_pts": "แต้ม",
        "col_ppm": "แต้ม/นัด", "col_left": "เหลือ", "col_max": "สูงสุด",
        "tip_mp": "จำนวนนัดที่แข่ง", "tip_w": "", "tip_d": "", "tip_l": "",
        "tip_gf": "เกมที่ได้", "tip_ga": "เกมที่เสีย", "tip_gd": "ผลต่างเกม",
        "tip_pts": "แต้มรวม", "tip_ppm": "แต้มเฉลี่ยต่อนัด",
        "tip_left": "คู่แข่งที่ยังไม่ได้แข่ง",
        "tip_max": "แต้มสูงสุดที่ยังทำได้ ถ้าแข่งครบทุกนัดที่เหลือ",
        "months": ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                   "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."],
        "year_offset": 543,
        "tba_text": "รอแข่ง",
        "tba_title": "ยังไม่ได้แข่ง — มีนัดไว้แล้ว",
        "ongoing_title": "กำลังแข่ง — ยังไม่นับในตารางคะแนน",
        "places_1": "{n} อันดับ", "places_n": "{n} อันดับ",
        "move_up": "ขึ้น {places} ตั้งแต่ {date}",
        "move_down": "ลง {places} ตั้งแต่ {date}",
        "move_same": "อันดับเท่าเดิมกับ {date}",
        "rules": "กติกา",
        "description": "ตารางคะแนนและผลการพบกันของลีกเทนนิส อัปเดต {date}",
        "standings": "ตารางคะแนน",
        "h2h": "ผลการพบกัน",
        "snapshot": "ข้อมูล ณ {date}",
        "source": "ที่มา: {file}",
        "rank_change_vs": "อันดับเทียบกับ {date}",
        "theme_toggle": "สลับโหมดมืด",
        "lang_toggle": "ภาษา",
        "axis_ATTACK": "บุก", "axis_DOMINANCE": "เหนือชั้น", "axis_FORM": "ฟอร์ม",
        "axis_DEFENSE": "รับ", "axis_CLUTCH": "ใจนิ่ง", "axis_MOVEMENT": "อันดับขยับ",
        "radar_label": "ค่าพลังผู้เล่น: {scores}",
        "compare_with": "เปรียบเทียบกับ",
        "choose_player": "เลือกผู้เล่น…",
        "tile_mp": "แข่ง", "tile_pts": "แต้ม", "tile_ppm": "แต้ม/นัด", "tile_sets": "เซต ชนะ–แพ้",
        "tile_close": "เซตสูสี", "tile_gf": "ได้", "tile_ga": "เสีย", "tile_gd": "ผลต่าง",
        "tile_rank": "อันดับ", "wdl": "ชนะ–เสมอ–แพ้",
        "w": "ช", "d": "ส", "l": "พ",
        "record": "ชนะ {w}{sep}เสมอ {d}{sep}แพ้ {l}",
        "since": "ตั้งแต่ {date}",
        "in_progress": "กำลังแข่ง",
        "no_matches": "ยังไม่มีผลการแข่งขัน",
        "close": "ปิด",
        "player_insights": "ค่าพลังผู้เล่น",
        "insights_sub": "ตลอดฤดูกาล · คะแนนเต็ม 10",
        "results": "ผลการแข่งขัน",
        "share_card": "แชร์รูปการ์ด",
        "compare": "เปรียบเทียบ",
        "share_compare": "แชร์รูปเปรียบเทียบ",
        "tap_to_skip": "แตะเพื่อข้าม",
        "classic_view": "มุมมองคลาสสิก",
        "mp_count": "{n} นัด",
        "wins": "ชนะ", "draws": "เสมอ", "losses": "แพ้",
        "games_bar": "ได้ {gf} เกม เสีย {ga} เกม",
        "game_diff": "ผลต่างเกม",
        "pts_small": "แต้ม",
        "ppm_suffix": "{ppm}/นัด",
        "ppm_title": "แต้มเฉลี่ยต่อนัด",
        "beta_suffix": "เบต้า",
        "progress": "แข่งไปแล้ว {done} / {total} นัด ({pct}%)",
        "still_to_play": "นัดที่เหลือ",
        "max_possible": "แต้มสูงสุดที่ทำได้: {n} แต้ม ถ้าแข่งครบทุกนัดที่เหลือ",
        "all_played": "แข่งครบทุกคู่แล้ว",
        "left_max": "เหลือ {left} · สูงสุด {max}",
    },
}


def t(lang, key, **kw):
    value = TEXT[lang][key]
    return value.format(**kw) if kw else value


def te(lang, key, **kw):
    """t(), HTML-escaped: use this wherever a string lands in markup or an attribute."""
    return html.escape(t(lang, key, **kw))


def record_text(row, lang, sep=" · "):
    """W/D/L line, e.g. `2W · 1D · 0L` or `ชนะ 2 · เสมอ 1 · แพ้ 0`."""
    return t(lang, "record", w=row["w"], d=row["d"], l=row["l"], sep=sep)


def outcome_letter(outcome, lang):
    """Single-letter chip for a win/draw/loss outcome, `?` when unknown."""
    return t(lang, outcome[0]) if outcome else "?"


def find_latest_snapshot(csv_dir):
    candidates = [p for p in csv_dir.glob("*.csv") if SNAPSHOT_RE.match(p.name)]
    if not candidates:
        raise SystemExit(f"No snapshot CSVs (YYYYMMDD.csv) found in {csv_dir}")
    return max(candidates, key=lambda p: p.name)


def find_previous_snapshot(csv_dir, latest):
    """The snapshot just before `latest` (same lexicographic order), or None."""
    earlier = [
        p
        for p in csv_dir.glob("*.csv")
        if SNAPSHOT_RE.match(p.name) and p.name < latest.name
    ]
    return max(earlier, key=lambda p: p.name) if earlier else None


def parse_snapshot(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    sep_idx = next(
        i for i, row in enumerate(rows) if all(cell.strip() == "" for cell in row)
    )

    standings = []
    for row in rows[1:sep_idx]:
        if all(cell.strip() == "" for cell in row):
            continue
        standings.append(
            {
                "rank": row[0].strip(),
                "name": row[1].strip(),
                "mp": row[2].strip(),
                "w": row[3].strip(),
                "d": row[4].strip(),
                "l": row[5].strip(),
                "gf": row[6].strip(),
                "ga": row[7].strip(),
                "gd": row[8].strip(),
                "pts": row[9].strip(),
                "rules": row[10].strip() if len(row) > 10 else "",
            }
        )

    h2h_header = rows[sep_idx + 1]
    players = [p.strip() for p in h2h_header[1:] if p.strip()]

    grid = {}
    for row in rows[sep_idx + 2 :]:
        if not row or all(cell.strip() == "" for cell in row):
            continue
        row_player = row[0].strip()
        grid[row_player] = {}
        for col_player, raw in zip(players, row[1:]):
            grid[row_player][col_player] = raw.strip()

    standings_names = {s["name"] for s in standings}
    if standings_names != set(players):
        print(
            "warning: standings and head-to-head player lists differ: "
            f"{standings_names.symmetric_difference(players)}",
            file=sys.stderr,
        )

    return standings, players, grid


def classify_cell(raw, row_player, col_player, lang="en"):
    if row_player == col_player:
        return "diag", "", None
    if raw == "":
        return "empty", "", None
    if raw.upper() == "TBA":
        return "tba", t(lang, "tba_text"), t(lang, "tba_title")
    set_count = raw.count(",") + 1
    if set_count < 2:
        return "ongoing", raw, t(lang, "ongoing_title")
    return "result", raw, None


def to_int(value):
    try:
        return int(value)
    except ValueError:
        return None


def compute_rank_moves(standings, prev_standings):
    """Places gained per player since the previous snapshot (positive = moved up).

    Display-only. Players absent from the previous snapshot, or with a
    non-integer rank in either one, get no entry.
    """
    prev_ranks = {s["name"]: to_int(s["rank"]) for s in prev_standings}
    moves = {}
    for s in standings:
        prev, cur = prev_ranks.get(s["name"]), to_int(s["rank"])
        if prev is not None and cur is not None:
            moves[s["name"]] = prev - cur
    return moves


def format_pts_per_match(row):
    """Display-only points per match played; an en dash when there is no MP yet."""
    pts, mp = to_int(row["pts"]), to_int(row["mp"])
    if pts is None or not mp:
        return "–"
    return f"{pts / mp:.2f}"


def format_max_points(row, stats):
    pts = to_int(row["pts"])
    return "–" if pts is None else str(pts + POINTS_PER_WIN * len(stats["remaining"]))


def render_league_progress(players, grid, lang):
    pairs = [(a, b) for i, a in enumerate(players) for b in players[i + 1:]]
    done = sum(
        1 for a, b in pairs
        if "result" in (
            classify_cell(grid.get(a, {}).get(b, ""), a, b)[0],
            classify_cell(grid.get(b, {}).get(a, ""), b, a)[0],
        )
    )
    total = len(pairs)
    pct = round(done / total * 100)
    return (
        f'    <div class="league-progress"><span>{te(lang, "progress", done=done, total=total, pct=pct)}</span>'
        f'<i class="lp-bar" role="presentation"><i style="width:{pct}%"></i></i></div>\n'
    )


def render_rank_move(delta, prev_label, lang):
    places = t(lang, "places_1" if abs(delta) == 1 else "places_n", n=abs(delta))
    if delta > 0:
        cls, text, title = "up", f"▲{delta}", t(lang, "move_up", places=places, date=prev_label)
    elif delta < 0:
        cls, text, title = "down", f"▼{-delta}", t(lang, "move_down", places=places, date=prev_label)
    else:
        cls, text, title = "same", "–", t(lang, "move_same", date=prev_label)
    return (
        f'<span class="rank-move {cls}" title="{html.escape(title)}" '
        f'aria-label="{html.escape(title)}">{text}</span>'
    )


def render_standings_table(standings, player_data, lang, moves=None, prev_label=None):
    def th(key, numeric):
        tip = TEXT[lang].get(f"tip_{key}")
        attrs = (' class="num"' if numeric else "") + (f' title="{html.escape(tip)}"' if tip else "")
        return f"<th{attrs}>{te(lang, 'col_' + key)}</th>"

    thead_cells = "".join(th(key, numeric) for key, numeric in STANDINGS_COLUMNS)

    body_rows = []
    for row_data in standings:
        stats = player_data[row_data["name"]][0]
        values = {
            **row_data,
            "ppm": format_pts_per_match(row_data),
            "left": str(len(stats["remaining"])),
            "max": format_max_points(row_data, stats),
        }
        cells = []
        for key, numeric in STANDINGS_COLUMNS:
            value = html.escape(values[key])
            if key == "name":
                value = render_player_link(row_data["name"])
            if key == "rank" and moves and row_data["name"] in moves:
                value += " " + render_rank_move(moves[row_data["name"]], prev_label, lang)
            cls = ' class="num"' if numeric else ""
            cells.append(f"<td{cls}>{value}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        "<table>\n"
        f"<thead><tr>{thead_cells}</tr></thead>\n"
        f"<tbody>{''.join(body_rows)}</tbody>\n"
        "</table>"
    )


def render_rules_section(standings, lang, section_class=None):
    items = [s for s in standings if s["rules"]]
    if not items:
        return ""

    list_items = "".join(
        f'<li><span class="badge">{html.escape(s["rules"].replace("📌", "").strip())}</span></li>'
        for s in items
    )

    section_attr = f' class="{section_class}"' if section_class else ""
    return (
        f"  <section{section_attr}>\n"
        f"    <h2>{te(lang, 'rules')}</h2>\n"
        f'    <ul class="rules-list">{list_items}</ul>\n'
        "  </section>\n"
    )


def render_h2h_table(players, grid, lang, linked=frozenset()):
    def name_cell(p):
        return render_player_link(p) if p in linked else html.escape(p)

    header_cells = "".join(f"<th>{name_cell(p)}</th>" for p in players)

    body_rows = []
    for row_player in players:
        row_cells = [f"<th>{name_cell(row_player)}</th>"]
        for col_player in players:
            raw = grid.get(row_player, {}).get(col_player, "")
            cls, text, title = classify_cell(raw, row_player, col_player, lang)
            title_attr = f' title="{html.escape(title)}"' if title else ""
            row_cells.append(
                f'<td class="cell-{cls}"{title_attr}>{html.escape(text)}</td>'
            )
        body_rows.append(f"<tr>{''.join(row_cells)}</tr>")

    return (
        '<table class="h2h">\n'
        f'<thead><tr><th>vs</th>{header_cells}</tr></thead>\n'
        f"<tbody>{''.join(body_rows)}</tbody>\n"
        "</table>"
    )


def format_snapshot_date(path, lang="en"):
    """`19 Sep 2026` in English; Thai month and Buddhist Era year, `19 ก.ย. 2569`."""
    stem = path.stem  # YYYYMMDD
    year, month, day = int(stem[0:4]), int(stem[4:6]), int(stem[6:8])
    month_name = TEXT[lang]["months"][month - 1]
    return f"{day} {month_name} {year + TEXT[lang]['year_offset']}"


SITE_URL = "https://pj-cup.github.io/"
SITE_TITLE = "PJ Cup Season1"


def page_url(lang, page):
    """Public URL of a page; the Thai index is the site root."""
    name = LANGS[lang][page]
    return SITE_URL if name == "index.html" else f"{SITE_URL}{name}"


def lang_head(lang, page):
    """`lang`, og:locale, hreflang alternates and the TH/EN switch for one page."""
    # The beta pages are noindex, so search engines would ignore their alternates.
    alt_links = "" if page == "beta" else "".join(
        f'<link rel="alternate" hreflang="{code}" href="{page_url(code, page)}">\n'
        for code in LANGS
    ) + f'<link rel="alternate" hreflang="x-default" href="{page_url("th", page)}">'
    # "./" rather than "index.html", so the Thai index keeps the site-root URL used everywhere else.
    links = "".join(
        f'<span aria-current="true">{info["label"]}</span>' if code == lang
        else f'<a href="{"./" if info[page] == "index.html" else info[page]}" hreflang="{code}" '
        f'lang="{code}">{info["label"]}</a>'
        for code, info in LANGS.items()
    )
    return {
        "lang": lang,
        "og_locale": LANGS[lang]["locale"],
        "alt_links": alt_links,
        "lang_toggle": (
            f'<nav class="lang-toggle" aria-label="{te(lang, "lang_toggle")}">'
            f"{links}</nav>"
        ),
    }


def render_page(
    lang, standings_html, rules_html, h2h_html, source_path, snapshot_date, standings_note="",
    player_cards="", compare="", league_progress_html="",
):
    template = Template((TEMPLATE_DIR / "index.html.tmpl").read_text(encoding="utf-8"))
    title = SITE_TITLE
    description = t(lang, "description", date=snapshot_date)
    return template.substitute(
        **lang_head(lang, "index"),
        title=title,
        description=html.escape(description),
        page_url=page_url(lang, "index"),
        image_url=f"{SITE_URL}logo.png",
        l_snapshot=te(lang, "snapshot", date=snapshot_date),
        l_theme_toggle=te(lang, "theme_toggle"),
        l_standings=te(lang, "standings"),
        l_h2h=te(lang, "h2h"),
        l_source=te(lang, "source", file=f"csv/{source_path.name}"),
        standings_note=standings_note,
        league_progress=league_progress_html,
        standings_table=standings_html,
        rules_section=rules_html,
        h2h_table=h2h_html,
        player_cards=player_cards,
        compare=compare,
    )


SET_SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")


def cell_outcome(raw):
    """Display-only win/draw/loss for a completed cell; never feeds the standings."""
    scores = [(int(a), int(b)) for a, b in SET_SCORE_RE.findall(raw)]
    if not scores:
        return ""
    won = sum(a > b for a, b in scores)
    lost = sum(a < b for a, b in scores)
    return "win" if won > lost else "loss" if lost > won else "draw"


# ---------- player cards (index.html only; all display-only) ----------

# Clockwise from the top of the hexagon.
INSIGHT_AXES = ("ATTACK", "DOMINANCE", "FORM", "DEFENSE", "CLUTCH", "MOVEMENT")
GAMES_PER_SET = 4
POINTS_PER_WIN = 3


def axis_label(axis, lang):
    """Display label for an INSIGHT_AXES key (the keys themselves never change)."""
    return t(lang, f"axis_{axis}")


def player_slug(name):
    return "player-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "x")


def compare_key(name):
    """Player slug without the prefix; compare deep links are #compare-<a>-vs-<b>."""
    return player_slug(name).removeprefix("player-")


def render_player_link(name):
    return (
        f'<a class="player-link" href="#{player_slug(name)}">{html.escape(name)}</a>'
    )


def player_match_stats(name, players, grid):
    """Set/game tallies from the player's own head-to-head row (their perspective).

    Only completed cells count; single-set cells are listed as in progress and
    empty/TBA cells are skipped, exactly as classify_cell() decides.
    """
    stats = {
        "sets_w": 0, "sets_l": 0, "games_w": 0, "games_l": 0,
        "close_w": 0, "close_l": 0, "dominant_w": 0,
        "results": [], "ongoing": [], "remaining": [],
    }
    for opp in players:
        cls, text, _ = classify_cell(grid.get(name, {}).get(opp, ""), name, opp)
        if cls not in ("result", "diag"):
            stats["remaining"].append((opp, cls))
        if cls == "ongoing":
            stats["ongoing"].append((opp, text))
        if cls != "result":
            continue
        for a, b in ((int(a), int(b)) for a, b in SET_SCORE_RE.findall(text)):
            stats["games_w"] += a
            stats["games_l"] += b
            if a > b:
                stats["sets_w"] += 1
            elif b > a:
                stats["sets_l"] += 1
            if abs(a - b) == 1:
                stats["close_w" if a > b else "close_l"] += 1
            if a - b >= 3:
                stats["dominant_w"] += 1
        stats["results"].append((opp, text, cell_outcome(text)))
    return stats


def clamp10(value):
    return max(0.0, min(10.0, value))


def compute_player_data(standings, players, grid, moves):
    """{name: (match stats, insight axes)} per standings row; language-independent, so built once."""
    data = {}
    for row in standings:
        stats = player_match_stats(row["name"], players, grid)
        data[row["name"]] = (stats, player_insights(row, stats, (moves or {}).get(row["name"])))
    return data


def player_insights(row, stats, move):
    """Six 0–10 scores in INSIGHT_AXES order; None where there is no data yet."""
    sets = stats["sets_w"] + stats["sets_l"]
    close = stats["close_w"] + stats["close_l"]
    pts, mp = to_int(row["pts"]), to_int(row["mp"])
    scores = {
        "ATTACK": clamp10(stats["games_w"] / sets / GAMES_PER_SET * 10) if sets else None,
        "DEFENSE": clamp10((1 - stats["games_l"] / sets / GAMES_PER_SET) * 10) if sets else None,
        "DOMINANCE": stats["dominant_w"] / sets * 10 if sets else None,
        "CLUTCH": stats["close_w"] / close * 10 if close else None,
        "FORM": clamp10(pts / mp / POINTS_PER_WIN * 10) if pts is not None and mp else None,
        "MOVEMENT": clamp10(5 + move) if move is not None else None,
    }
    return [(axis, scores[axis]) for axis in INSIGHT_AXES]


def format_score(value):
    return "–" if value is None else f"{value:.1f}"


def top_axis(insights):
    """Index of the highest score (first on ties), or None when nothing is scored."""
    scored = [(v, -i) for i, (_, v) in enumerate(insights) if v is not None]
    return -max(scored)[1] if scored else None


def radar_point(cx, cy, radius, i):
    angle = math.radians(-90 + 60 * i)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def render_radar_svg(insights, lang):
    cx, cy, r, label_r = 190, 180, 95, 114
    top = top_axis(insights)

    def ring(frac):
        return " ".join(
            "{:.1f},{:.1f}".format(*radar_point(cx, cy, r * frac, i)) for i in range(6)
        )

    parts = [
        '<svg class="radar" viewBox="0 0 380 360" role="img" aria-label="'
        + te(lang, "radar_label", scores=", ".join(
            f"{axis_label(a, lang).title()} {format_score(v)}" for a, v in insights
        ))
        + '">',
        f'<polygon class="rg-area" points="{ring(1)}"/>',
    ]
    parts += [f'<polygon class="rg-ring" points="{ring(f)}"/>' for f in (0.25, 0.5, 0.75)]
    for i in range(6):
        x, y = radar_point(cx, cy, r, i)
        parts.append(f'<line class="rg-spoke" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>')
    parts.append(f'<polygon class="rg-outer" points="{ring(1)}"/>')
    for i in range(6):
        x, y = radar_point(cx, cy, r, i)
        parts.append(f'<circle class="rg-dot" cx="{x:.1f}" cy="{y:.1f}" r="3"/>')
    shape = " ".join(
        "{:.1f},{:.1f}".format(*radar_point(cx, cy, r * (v or 0) / 10, i))
        for i, (_, v) in enumerate(insights)
    )
    parts.append(f'<polygon class="rg-shape" points="{shape}"/>')
    parts.append(f'<circle class="rg-dot" cx="{cx}" cy="{cy}" r="2.5"/>')

    for i, (axis, value) in enumerate(insights):
        x, y = radar_point(cx, cy, label_r, i)
        if i == 0:
            anchor, ly, vy = "middle", y - 30, y - 2
        elif i == 3:
            anchor, ly, vy = "middle", y + 10, y + 38
        else:
            anchor, ly, vy = ("start" if i < 3 else "end"), y - 6, y + 22
        cls = " top" if i == top else ""
        parts.append(
            f'<text class="rg-label{cls}" x="{x:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{axis_label(axis, lang)}</text>'
            f'<text class="rg-value{cls}" x="{x:.1f}" y="{vy:.1f}" text-anchor="{anchor}">{format_score(value)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def format_delta(value):
    return f"+{value}" if value > 0 else ("0" if value == 0 else f"−{-value}")


def render_tiles(tiles, extra_cls=""):
    return f'<div class="pc-tiles{extra_cls}">' + "".join(
        f'<div class="pc-tile"><span>{html.escape(label)}</span><b>{value}</b></div>'
        for label, value in tiles
    ) + "</div>"


def render_compare_picker(name, standings, lang):
    options = "".join(
        f'<option value="{compare_key(s["name"])}">{html.escape(s["name"])}</option>'
        for s in standings if s["name"] != name
    )
    return (
        f'<label class="pc-compare" hidden><span>{te(lang, "compare_with")}</span>'
        f'<select><option value="">{te(lang, "choose_player")}</option>{options}</select></label>'
    )


def render_remaining_block(row, stats, lang):
    if not stats["remaining"]:
        return f'<div class="pc-block"><h4>{te(lang, "still_to_play")}</h4><p class="pc-empty">{te(lang, "all_played")}</p></div>'
    chips = "".join(
        f'<li class="{cls}">{render_player_link(opp)}</li>' for opp, cls in stats["remaining"]
    )
    return (
        f'<div class="pc-block"><h4>{te(lang, "still_to_play")} · {len(stats["remaining"])}</h4>'
        f'<p class="pc-sub">{te(lang, "max_possible", n=format_max_points(row, stats))}</p>'
        f'<ul class="pc-remaining">{chips}</ul></div>'
    )


def render_player_card(
    row, stats, insights, move, prev_row, prev_label, snapshot_date, standings, lang
):
    name = row["name"]
    slug = player_slug(name)
    close = stats["close_w"] + stats["close_l"]

    gd = to_int(row["gd"])
    gd_text = format_delta(gd) if gd is not None else row["gd"]
    tiles = [
        (t(lang, "tile_mp"), row["mp"]),
        (t(lang, "tile_pts"), row["pts"]),
        (t(lang, "tile_ppm"), format_pts_per_match(row)),
        (t(lang, "tile_sets"), f'{stats["sets_w"]}–{stats["sets_l"]}'),
        (t(lang, "tile_close"), f'{stats["close_w"]}–{stats["close_l"]}' if close else "–"),
        (t(lang, "tile_gf"), row["gf"]),
        (t(lang, "tile_ga"), row["ga"]),
        (t(lang, "tile_gd"), gd_text),
    ]
    record = record_text(row, lang)
    move_html = render_rank_move(move, prev_label, lang) if move is not None else ""

    since_html = ""
    if prev_row:
        since = []
        prev_rank, cur_rank = to_int(prev_row["rank"]), to_int(row["rank"])
        if prev_rank is not None and cur_rank is not None:
            since.append((t(lang, "tile_rank"), f"{prev_rank}→{cur_rank}"))
        for key, label in (("pts", t(lang, "tile_pts")), ("mp", t(lang, "tile_mp")), ("gd", t(lang, "tile_gd"))):
            cur, prev = to_int(row[key]), to_int(prev_row[key])
            if cur is not None and prev is not None:
                since.append((label, format_delta(cur - prev)))
        if since:
            since_html = (
                f'<div class="pc-block"><h4>{te(lang, "since", date=prev_label)}</h4>'
                + render_tiles([(l, html.escape(v)) for l, v in since], " small")
                + "</div>"
            )

    items = [
        f'<li><span class="chip {outcome}">{html.escape(outcome_letter(outcome, lang))}</span>'
        f'<span class="opp">{html.escape(opp)}</span><span class="score">{html.escape(text)}</span></li>'
        for opp, text, outcome in stats["results"]
    ] + [
        f'<li class="live"><span class="chip live">•</span><span class="opp">{html.escape(opp)}</span>'
        f'<span class="score">{html.escape(text)} <em>{te(lang, "in_progress")}</em></span></li>'
        for opp, text in stats["ongoing"]
    ]
    results_html = (
        f'<ul class="pc-results">{"".join(items)}</ul>'
        if items else f'<p class="pc-empty">{te(lang, "no_matches")}</p>'
    )

    share = {
        "slug": slug,
        "name": name,
        "rank": row["rank"],
        "move": move,
        "record": record_text(row, lang, "  "),
        "tiles": tiles,
        "axes": [[axis_label(axis, lang), None if v is None else round(v, 1)] for axis, v in insights],
        "top": top_axis(insights),
        "sub": t(lang, "insights_sub"),
        "date": snapshot_date,
        "site": SITE_TITLE,
        "url": SITE_URL.removeprefix("https://").rstrip("/"),
        "page": page_url(lang, "index"),
    }
    share_attr = html.escape(json.dumps(share, ensure_ascii=False, separators=(",", ":")))

    return (
        f'<dialog class="player-card" id="{slug}" aria-labelledby="{slug}-name" data-share="{share_attr}">'
        f'<div class="pc-inner">'
        f'<div class="pc-head"><span class="pc-rank">{html.escape(row["rank"])}</span>'
        f'<div class="pc-id"><h3 id="{slug}-name">{html.escape(name)}</h3>'
        f'<p class="pc-record">{html.escape(record)}{move_html}</p></div>'
        f'<a class="pc-close" href="#" aria-label="{te(lang, "close")}">&times;</a></div>'
        + render_tiles([(l, html.escape(v)) for l, v in tiles])
        + f'<div class="pc-block pc-insights"><h4>{te(lang, "player_insights")}</h4>'
        f'<p class="pc-sub">{te(lang, "insights_sub")}</p>{render_radar_svg(insights, lang)}</div>'
        + since_html
        + f'<div class="pc-block"><h4>{te(lang, "results")}</h4>{results_html}</div>'
        + render_remaining_block(row, stats, lang)
        + f'<div class="pc-actions">{render_compare_picker(name, standings, lang)}'
        f'<button class="pc-share" type="button" hidden>{te(lang, "share_card")}</button></div>'
        f"</div></dialog>"
    )


def render_player_cards(
    standings, player_data, moves, prev_standings, prev_label, snapshot_date, lang
):
    prev_rows = {s["name"]: s for s in prev_standings or []}
    cards = [
        render_player_card(
            row, *player_data[row["name"]], (moves or {}).get(row["name"]),
            prev_rows.get(row["name"]), prev_label, snapshot_date, standings, lang,
        )
        for row in standings
    ]
    return "\n".join(cards)


# ---------- player compare (index.html only; filled in by player-card.js) ----------


def build_compare_data(standings, players, grid, player_data, moves, snapshot_date, lang):
    """Per-player stats + head-to-head cells for any pair, as JSON for the compare dialog."""
    data = {}
    for row in standings:
        name = row["name"]
        move = (moves or {}).get(name)
        stats, insights = player_data[name]
        data[compare_key(name)] = {
            "name": name,
            "rank": row["rank"],
            "move": move,
            "record": record_text(row, lang),
            **{key: to_int(row[key]) for key in ("mp", "w", "d", "l", "pts", "gf", "ga", "gd")},
            "ppm": format_pts_per_match(row),
            **{key: stats[key] for key in ("sets_w", "sets_l", "close_w", "close_l")},
            "axes": [[axis_label(axis, lang), None if v is None else round(v, 1)] for axis, v in insights],
            "top": top_axis(insights),
        }
    h2h = {}
    for a in players:
        for b in players:
            cls, text, _ = classify_cell(grid.get(a, {}).get(b, ""), a, b)
            if cls in ("result", "ongoing"):
                h2h.setdefault(compare_key(a), {})[compare_key(b)] = [cls, text, cell_outcome(text) if cls == "result" else ""]
    return {
        "players": data,
        "h2h": h2h,
        "axes": [axis_label(axis, lang) for axis in INSIGHT_AXES],
        "letters": {o: outcome_letter(o, lang) for o in ("win", "draw", "loss")},
        # Same labels as the card tiles, so the compare rows can't drift from them.
        "labels": {
            **{key: t(lang, "tile_" + key) for key in ("rank", "mp", "pts", "ppm", "sets", "close", "gf", "ga", "gd")},
            "wdl": t(lang, "wdl"),
            "h2h": t(lang, "h2h"),
            "insights": t(lang, "player_insights"),
            "sub": t(lang, "insights_sub"),
        },
        "date": snapshot_date,
        "site": SITE_TITLE,
        "url": SITE_URL.removeprefix("https://").rstrip("/"),
        "page": page_url(lang, "index"),
    }


def render_compare(compare_data, lang):
    payload = json.dumps(compare_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        '<dialog class="player-card compare-card" id="compare" aria-labelledby="compare-title">'
        '<div class="pc-inner">'
        f'<div class="pc-head"><h3 class="cmp-title" id="compare-title">{te(lang, "compare")}</h3>'
        f'<a class="pc-close" href="#" aria-label="{te(lang, "close")}">&times;</a></div>'
        '<div class="cmp-body"></div>'
        f'<div class="pc-actions"><button class="pc-share" type="button" hidden>{te(lang, "share_compare")}</button></div>'
        "</div></dialog>\n"
        f'<script type="application/json" id="compare-data">{payload}</script>'
    )


def render_title_letters(title):
    return "".join(
        f'<span class="ltr" style="--i:{i}">{"&nbsp;" if ch == " " else html.escape(ch)}</span>'
        for i, ch in enumerate(title)
    )


def render_beta_standings(standings, player_data, lang, moves=None, prev_label=None):
    cards = []
    for i, s in enumerate(standings):
        name = html.escape(s["name"])
        rank = html.escape(s["rank"])
        medal = f" medal-{s['rank']}" if s["rank"] in ("1", "2", "3") else ""
        leader = " leader" if s["rank"] == "1" else ""

        gf, ga = to_int(s["gf"]) or 0, to_int(s["ga"]) or 0
        share = f"{gf / (gf + ga) * 100:.1f}" if gf + ga else "0"
        bar_cls = "bar" if gf + ga else "bar empty"

        gd_text, gd_cls = html.escape(s["gd"]), "zero"
        gd = to_int(s["gd"])
        if gd is not None and gd > 0:
            gd_text, gd_cls = f"+{gd}", "pos"
        elif gd is not None and gd < 0:
            gd_cls = "neg"

        pts = html.escape(s["pts"])
        ppm = format_pts_per_match(s)
        ppm_text = ppm if ppm == "–" else te(lang, "ppm_suffix", ppm=ppm)
        move = render_rank_move(moves[s["name"]], prev_label, lang) if moves and s["name"] in moves else ""
        stats = player_data[s["name"]][0]
        left_text = te(lang, "left_max", left=len(stats["remaining"]), max=format_max_points(s, stats))
        cards.append(
            f'<li class="card{leader}" style="--i:{i}"><div class="inner">'
            f'<span class="rankcol"><span class="rank{medal}">{rank}</span>{move}</span>'
            f'<div class="who"><span class="name">{name}</span>'
            f'<span class="mp">{te(lang, "mp_count", n=s["mp"])}</span></div>'
            f'<div class="pills">'
            f'<span class="pill w" title="{te(lang, "wins")}"><b>{html.escape(s["w"])}</b>{te(lang, "w")}</span>'
            f'<span class="pill d" title="{te(lang, "draws")}"><b>{html.escape(s["d"])}</b>{te(lang, "d")}</span>'
            f'<span class="pill l" title="{te(lang, "losses")}"><b>{html.escape(s["l"])}</b>{te(lang, "l")}</span>'
            f"</div>"
            f'<div class="gfga">'
            f'<div class="{bar_cls}" role="img" aria-label="{te(lang, "games_bar", gf=gf, ga=ga)}">'
            f'<i class="fill" style="--share:{share}"></i></div>'
            f'<span class="nums">{te(lang, "tile_gf")} <b>{html.escape(s["gf"])}</b> · '
            f'{te(lang, "tile_ga")} <b>{html.escape(s["ga"])}</b></span>'
            f"</div>"
            f'<span class="gd {gd_cls}" title="{te(lang, "game_diff")}">{gd_text}</span>'
            f'<span class="pts"><b class="count" data-to="{pts}">{pts}</b><small>{te(lang, "pts_small")}</small>'
            f'<small class="ppm" title="{te(lang, "ppm_title")}">{ppm_text}</small>'
            f'<small class="left" title="{te(lang, "tip_max")}">{left_text}</small></span>'
            f"</div></li>"
        )
    return f'    <ol class="board">{"".join(cards)}</ol>'


def render_beta_h2h(players, grid, lang):
    header_cells = "".join(f"<th>{html.escape(p)}</th>" for p in players)

    body_rows = []
    for r, row_player in enumerate(players):
        row_cells = [f"<th>{html.escape(row_player)}</th>"]
        for c, col_player in enumerate(players):
            raw = grid.get(row_player, {}).get(col_player, "")
            cls, text, title = classify_cell(raw, row_player, col_player, lang)
            title_attr = f' title="{html.escape(title)}"' if title else ""
            inner = html.escape(text)
            if cls == "result":
                outcome = cell_outcome(text)
                if outcome:
                    cls += f" out-{outcome}"
                    inner = (
                        f'<b class="wdl">{html.escape(outcome_letter(outcome, lang))}</b>'
                        f'<span class="sc">{inner}</span>'
                    )
            row_cells.append(
                f'<td class="cell-{cls}" style="--d:{(r + c) * 30}ms"{title_attr}>{inner}</td>'
            )
        body_rows.append(f"<tr>{''.join(row_cells)}</tr>")

    return (
        '<table class="h2h">\n'
        f"<thead><tr><th>vs</th>{header_cells}</tr></thead>\n"
        f"<tbody>{''.join(body_rows)}</tbody>\n"
        "</table>"
    )


def render_beta_page(
    lang, standings, players, grid, player_data, source_path, snapshot_date,
    moves=None, prev_label=None, standings_note="", league_progress_html="",
):
    template = Template((TEMPLATE_DIR / "beta.html.tmpl").read_text(encoding="utf-8"))
    description = t(lang, "description", date=snapshot_date)
    return template.substitute(
        **lang_head(lang, "beta"),
        title=SITE_TITLE,
        description=html.escape(description),
        page_url=page_url(lang, "beta"),
        image_url=f"{SITE_URL}logo.png",
        l_beta=te(lang, "beta_suffix"),
        l_snapshot=te(lang, "snapshot", date=snapshot_date),
        l_tap_to_skip=te(lang, "tap_to_skip"),
        l_classic_view=te(lang, "classic_view"),
        classic_href=LANGS[lang]["index"],
        l_standings=te(lang, "standings"),
        l_h2h=te(lang, "h2h"),
        l_source=te(lang, "source", file=f"csv/{source_path.name}"),
        title_letters=render_title_letters(SITE_TITLE),
        standings_note=standings_note,
        league_progress=league_progress_html,
        standings_board=render_beta_standings(standings, player_data, lang, moves, prev_label),
        rules_section=render_rules_section(standings, lang, section_class="reveal"),
        h2h_table=render_beta_h2h(players, grid, lang),
    )


def main():
    latest = find_latest_snapshot(CSV_DIR)
    print(f"Using latest snapshot: {latest.relative_to(ROOT)}")

    standings, players, grid = parse_snapshot(latest)

    moves, prev_standings = None, None
    previous = find_previous_snapshot(CSV_DIR, latest)
    if previous:
        print(f"Comparing ranks with: {previous.relative_to(ROOT)}")
        prev_standings, _, _ = parse_snapshot(previous)
        moves = compute_rank_moves(standings, prev_standings)

    player_data = compute_player_data(standings, players, grid, moves)

    DOCS_DIR.mkdir(exist_ok=True)
    written = []
    for lang, pages in LANGS.items():
        snapshot_date = format_snapshot_date(latest, lang)
        prev_label, standings_note = None, ""
        if previous:
            prev_label = format_snapshot_date(previous, lang)
            standings_note = (
                '    <p class="standings-note">'
                f'{te(lang, "rank_change_vs", date=prev_label)}</p>\n'
            )

        standings_html = render_standings_table(standings, player_data, lang, moves, prev_label)
        progress_html = render_league_progress(players, grid, lang)
        rules_html = render_rules_section(standings, lang)
        h2h_html = render_h2h_table(players, grid, lang, linked={s["name"] for s in standings})
        player_cards = render_player_cards(
            standings, player_data, moves, prev_standings, prev_label, snapshot_date, lang
        )
        compare_html = render_compare(
            build_compare_data(standings, players, grid, player_data, moves, snapshot_date, lang), lang
        )
        page_html = render_page(
            lang, standings_html, rules_html, h2h_html, latest, snapshot_date, standings_note,
            player_cards, compare_html, progress_html,
        )

        (DOCS_DIR / pages["index"]).write_text(page_html, encoding="utf-8")
        (DOCS_DIR / pages["beta"]).write_text(
            render_beta_page(
                lang, standings, players, grid, player_data, latest, snapshot_date, moves,
                prev_label, standings_note, progress_html,
            ),
            encoding="utf-8",
        )
        written += [pages["index"], pages["beta"]]
    (DOCS_DIR / "beta.css").write_text(
        (TEMPLATE_DIR / "beta.css.tmpl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (DOCS_DIR / "beta.js").write_text(
        (TEMPLATE_DIR / "beta.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (DOCS_DIR / "style.css").write_text(
        (TEMPLATE_DIR / "style.css.tmpl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (DOCS_DIR / "theme.js").write_text(
        (TEMPLATE_DIR / "theme.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (DOCS_DIR / "player-card.js").write_text(
        (TEMPLATE_DIR / "player-card.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    shutil.copyfile(LOGO_SOURCE, DOCS_DIR / "logo.png")

    print(
        f"Wrote {', '.join(str(DOCS_DIR / n) for n in written)}, {DOCS_DIR / 'style.css'}, "
        f"{DOCS_DIR / 'theme.js'}, {DOCS_DIR / 'player-card.js'}, {DOCS_DIR / 'logo.png'} (from {LOGO_SOURCE.relative_to(ROOT)})"
    )
    print(f"Players: {len(players)}, standings rows: {len(standings)}")


if __name__ == "__main__":
    main()
