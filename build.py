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
    ("rank", "#", False),
    ("name", "Player", False),
    ("mp", "MP", True),
    ("w", "W", True),
    ("d", "D", True),
    ("l", "L", True),
    ("gf", "GF", True),
    ("ga", "GA", True),
    ("gd", "GD", True),
    ("pts", "Pts", True),
    ("ppm", "Pts/MP", True),
]


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


def classify_cell(raw, row_player, col_player):
    if row_player == col_player:
        return "diag", "", None
    if raw == "":
        return "empty", "", None
    if raw.upper() == "TBA":
        return "tba", "TBA", "Not played yet — planned to play"
    set_count = raw.count(",") + 1
    if set_count < 2:
        return "ongoing", raw, "Match in progress — not yet counted in standings"
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


def render_rank_move(delta, prev_label):
    places = f"{abs(delta)} place{'s' if abs(delta) != 1 else ''}"
    if delta > 0:
        cls, text, title = "up", f"▲{delta}", f"Up {places} since {prev_label}"
    elif delta < 0:
        cls, text, title = "down", f"▼{-delta}", f"Down {places} since {prev_label}"
    else:
        cls, text, title = "same", "–", f"Same rank as {prev_label}"
    return (
        f'<span class="rank-move {cls}" title="{html.escape(title)}" '
        f'aria-label="{html.escape(title)}">{text}</span>'
    )


def render_standings_table(standings, moves=None, prev_label=None):
    thead_cells = "".join(
        f'<th class="num">{label}</th>' if numeric else f"<th>{label}</th>"
        for _, label, numeric in STANDINGS_COLUMNS
    )

    body_rows = []
    for row_data in standings:
        values = {**row_data, "ppm": format_pts_per_match(row_data)}
        cells = []
        for key, _, numeric in STANDINGS_COLUMNS:
            value = html.escape(values[key])
            if key == "name":
                value = render_player_link(row_data["name"])
            if key == "rank" and moves and row_data["name"] in moves:
                value += " " + render_rank_move(moves[row_data["name"]], prev_label)
            cls = ' class="num"' if numeric else ""
            cells.append(f"<td{cls}>{value}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        "<table>\n"
        f"<thead><tr>{thead_cells}</tr></thead>\n"
        f"<tbody>{''.join(body_rows)}</tbody>\n"
        "</table>"
    )


def render_rules_section(standings, section_class=None):
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
        "    <h2>Rules</h2>\n"
        f'    <ul class="rules-list">{list_items}</ul>\n'
        "  </section>\n"
    )


def render_h2h_table(players, grid, linked=frozenset()):
    def name_cell(p):
        return render_player_link(p) if p in linked else html.escape(p)

    header_cells = "".join(f"<th>{name_cell(p)}</th>" for p in players)

    body_rows = []
    for row_player in players:
        row_cells = [f"<th>{name_cell(row_player)}</th>"]
        for col_player in players:
            raw = grid.get(row_player, {}).get(col_player, "")
            cls, text, title = classify_cell(raw, row_player, col_player)
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


def format_snapshot_date(path):
    stem = path.stem  # YYYYMMDD
    year, month, day = stem[0:4], stem[4:6], stem[6:8]
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    return f"{int(day)} {months[int(month) - 1]} {year}"


SITE_URL = "https://pj-cup.github.io/"
SITE_TITLE = "PJ Cup Season1"


def render_page(
    standings_html, rules_html, h2h_html, source_path, snapshot_date, standings_note="",
    player_cards="",
):
    template = Template((TEMPLATE_DIR / "index.html.tmpl").read_text(encoding="utf-8"))
    title = SITE_TITLE
    description = f"Tennis league standings and head-to-head results, updated {snapshot_date}."
    return template.substitute(
        title=title,
        description=html.escape(description),
        page_url=SITE_URL,
        image_url=f"{SITE_URL}logo.png",
        snapshot_date=snapshot_date,
        source_file=f"csv/{source_path.name}",
        standings_note=standings_note,
        standings_table=standings_html,
        rules_section=rules_html,
        h2h_table=h2h_html,
        player_cards=player_cards,
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
INSIGHT_AXES = ("ATTACK", "DOMINANCE", "FORM", "MOVEMENT", "CLUTCH", "DEFENSE")
GAMES_PER_SET = 4


def player_slug(name):
    return "player-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "x")


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
        "results": [], "ongoing": [],
    }
    for opp in players:
        cls, text, _ = classify_cell(grid.get(name, {}).get(opp, ""), name, opp)
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
        "FORM": clamp10(pts / mp / 3 * 10) if pts is not None and mp else None,
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


def render_radar_svg(insights):
    cx, cy, r, label_r = 190, 180, 95, 114
    top = top_axis(insights)

    def ring(frac):
        return " ".join(
            "{:.1f},{:.1f}".format(*radar_point(cx, cy, r * frac, i)) for i in range(6)
        )

    parts = [
        '<svg class="radar" viewBox="0 0 380 360" role="img" aria-label="Player insights: '
        + html.escape(", ".join(f"{a.title()} {format_score(v)}" for a, v in insights))
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
            f'<text class="rg-label{cls}" x="{x:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{axis}</text>'
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


def render_player_card(row, players, grid, move, prev_row, prev_label, snapshot_date):
    name = row["name"]
    slug = player_slug(name)
    stats = player_match_stats(name, players, grid)
    insights = player_insights(row, stats, move)
    close = stats["close_w"] + stats["close_l"]

    gd = to_int(row["gd"])
    gd_text = format_delta(gd) if gd is not None else row["gd"]
    tiles = [
        ("MP", row["mp"]),
        ("PTS", row["pts"]),
        ("PTS/MP", format_pts_per_match(row)),
        ("SETS W–L", f'{stats["sets_w"]}–{stats["sets_l"]}'),
        ("CLOSE", f'{stats["close_w"]}–{stats["close_l"]}' if close else "–"),
        ("GF", row["gf"]),
        ("GA", row["ga"]),
        ("GD", gd_text),
    ]
    record = f'{row["w"]}W · {row["d"]}D · {row["l"]}L'
    move_html = render_rank_move(move, prev_label) if move is not None else ""

    since_html = ""
    if prev_row:
        since = []
        prev_rank, cur_rank = to_int(prev_row["rank"]), to_int(row["rank"])
        if prev_rank is not None and cur_rank is not None:
            since.append(("RANK", f"{prev_rank}→{cur_rank}"))
        for key, label in (("pts", "PTS"), ("mp", "MP"), ("gd", "GD")):
            cur, prev = to_int(row[key]), to_int(prev_row[key])
            if cur is not None and prev is not None:
                since.append((label, format_delta(cur - prev)))
        if since:
            since_html = (
                f'<div class="pc-block"><h4>Since {html.escape(prev_label)}</h4>'
                + render_tiles([(l, html.escape(v)) for l, v in since], " small")
                + "</div>"
            )

    items = [
        f'<li><span class="chip {outcome}">{(outcome or "?")[0].upper()}</span>'
        f'<span class="opp">{html.escape(opp)}</span><span class="score">{html.escape(text)}</span></li>'
        for opp, text, outcome in stats["results"]
    ] + [
        f'<li class="live"><span class="chip live">•</span><span class="opp">{html.escape(opp)}</span>'
        f'<span class="score">{html.escape(text)} <em>in progress</em></span></li>'
        for opp, text in stats["ongoing"]
    ]
    results_html = (
        f'<ul class="pc-results">{"".join(items)}</ul>'
        if items else '<p class="pc-empty">No matches played yet.</p>'
    )

    share = {
        "slug": slug,
        "name": name,
        "rank": row["rank"],
        "move": move,
        "record": f'{row["w"]}W  {row["d"]}D  {row["l"]}L',
        "tiles": tiles,
        "axes": [[axis, None if v is None else round(v, 1)] for axis, v in insights],
        "top": top_axis(insights),
        "date": snapshot_date,
        "site": SITE_TITLE,
        "url": SITE_URL.removeprefix("https://").rstrip("/"),
    }
    share_attr = html.escape(json.dumps(share, ensure_ascii=False, separators=(",", ":")))

    return (
        f'<dialog class="player-card" id="{slug}" aria-labelledby="{slug}-name" data-share="{share_attr}">'
        f'<div class="pc-inner">'
        f'<div class="pc-head"><span class="pc-rank">{html.escape(row["rank"])}</span>'
        f'<div class="pc-id"><h3 id="{slug}-name">{html.escape(name)}</h3>'
        f'<p class="pc-record">{html.escape(record)}{move_html}</p></div>'
        f'<a class="pc-close" href="#" aria-label="Close">&times;</a></div>'
        + render_tiles([(l, html.escape(v)) for l, v in tiles])
        + f'<div class="pc-block pc-insights"><h4>Player Insights</h4>'
        f'<p class="pc-sub">Season to date · scores out of 10</p>{render_radar_svg(insights)}</div>'
        + since_html
        + f'<div class="pc-block"><h4>Results</h4>{results_html}</div>'
        f'<div class="pc-actions"><button class="pc-share" type="button" hidden>Share card image</button></div>'
        f"</div></dialog>"
    )


def render_player_cards(standings, players, grid, moves, prev_standings, prev_label, snapshot_date):
    prev_rows = {s["name"]: s for s in prev_standings or []}
    cards = [
        render_player_card(
            row, players, grid, (moves or {}).get(row["name"]),
            prev_rows.get(row["name"]), prev_label, snapshot_date,
        )
        for row in standings
    ]
    return "\n".join(cards)


def render_title_letters(title):
    return "".join(
        f'<span class="ltr" style="--i:{i}">{"&nbsp;" if ch == " " else html.escape(ch)}</span>'
        for i, ch in enumerate(title)
    )


def render_beta_standings(standings, moves=None, prev_label=None):
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
        ppm_text = ppm if ppm == "–" else f"{ppm}/MP"
        move = render_rank_move(moves[s["name"]], prev_label) if moves and s["name"] in moves else ""
        cards.append(
            f'<li class="card{leader}" style="--i:{i}"><div class="inner">'
            f'<span class="rankcol"><span class="rank{medal}">{rank}</span>{move}</span>'
            f'<div class="who"><span class="name">{name}</span>'
            f'<span class="mp">{html.escape(s["mp"])} MP</span></div>'
            f'<div class="pills">'
            f'<span class="pill w" title="Wins"><b>{html.escape(s["w"])}</b>W</span>'
            f'<span class="pill d" title="Draws"><b>{html.escape(s["d"])}</b>D</span>'
            f'<span class="pill l" title="Losses"><b>{html.escape(s["l"])}</b>L</span>'
            f"</div>"
            f'<div class="gfga">'
            f'<div class="{bar_cls}" role="img" aria-label="Games for {gf}, against {ga}">'
            f'<i class="fill" style="--share:{share}"></i></div>'
            f'<span class="nums">GF <b>{html.escape(s["gf"])}</b> · GA <b>{html.escape(s["ga"])}</b></span>'
            f"</div>"
            f'<span class="gd {gd_cls}" title="Game difference">{gd_text}</span>'
            f'<span class="pts"><b class="count" data-to="{pts}">{pts}</b><small>PTS</small>'
            f'<small class="ppm" title="Points per match played">{ppm_text}</small></span>'
            f"</div></li>"
        )
    return f'    <ol class="board">{"".join(cards)}</ol>'


def render_beta_h2h(players, grid):
    header_cells = "".join(f"<th>{html.escape(p)}</th>" for p in players)

    body_rows = []
    for r, row_player in enumerate(players):
        row_cells = [f"<th>{html.escape(row_player)}</th>"]
        for c, col_player in enumerate(players):
            raw = grid.get(row_player, {}).get(col_player, "")
            cls, text, title = classify_cell(raw, row_player, col_player)
            title_attr = f' title="{html.escape(title)}"' if title else ""
            inner = html.escape(text)
            if cls == "result":
                outcome = cell_outcome(text)
                if outcome:
                    cls += f" out-{outcome}"
                    inner = (
                        f'<b class="wdl">{outcome[0].upper()}</b>'
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
    standings, players, grid, source_path, snapshot_date,
    moves=None, prev_label=None, standings_note="",
):
    template = Template((TEMPLATE_DIR / "beta.html.tmpl").read_text(encoding="utf-8"))
    description = f"Tennis league standings and head-to-head results, updated {snapshot_date}."
    return template.substitute(
        title=SITE_TITLE,
        description=html.escape(description),
        page_url=f"{SITE_URL}beta.html",
        image_url=f"{SITE_URL}logo.png",
        snapshot_date=snapshot_date,
        source_file=f"csv/{source_path.name}",
        title_letters=render_title_letters(SITE_TITLE),
        standings_note=standings_note,
        standings_board=render_beta_standings(standings, moves, prev_label),
        rules_section=render_rules_section(standings, section_class="reveal"),
        h2h_table=render_beta_h2h(players, grid),
    )


def main():
    latest = find_latest_snapshot(CSV_DIR)
    print(f"Using latest snapshot: {latest.relative_to(ROOT)}")

    standings, players, grid = parse_snapshot(latest)
    snapshot_date = format_snapshot_date(latest)

    moves, prev_label, prev_standings, standings_note = None, None, None, ""
    previous = find_previous_snapshot(CSV_DIR, latest)
    if previous:
        print(f"Comparing ranks with: {previous.relative_to(ROOT)}")
        prev_standings, _, _ = parse_snapshot(previous)
        moves = compute_rank_moves(standings, prev_standings)
        prev_label = format_snapshot_date(previous)
        standings_note = (
            f'    <p class="standings-note">Rank change vs {html.escape(prev_label)}</p>\n'
        )

    standings_html = render_standings_table(standings, moves, prev_label)
    rules_html = render_rules_section(standings)
    h2h_html = render_h2h_table(players, grid, linked={s["name"] for s in standings})
    player_cards = render_player_cards(
        standings, players, grid, moves, prev_standings, prev_label, snapshot_date
    )
    page_html = render_page(
        standings_html, rules_html, h2h_html, latest, snapshot_date, standings_note,
        player_cards,
    )

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(page_html, encoding="utf-8")
    (DOCS_DIR / "beta.html").write_text(
        render_beta_page(
            standings, players, grid, latest, snapshot_date, moves, prev_label, standings_note
        ),
        encoding="utf-8",
    )
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
        f"Wrote {DOCS_DIR / 'index.html'}, {DOCS_DIR / 'style.css'}, "
        f"{DOCS_DIR / 'theme.js'}, {DOCS_DIR / 'player-card.js'}, {DOCS_DIR / 'logo.png'} (from {LOGO_SOURCE.relative_to(ROOT)})"
    )
    print(f"Players: {len(players)}, standings rows: {len(standings)}")


if __name__ == "__main__":
    main()
