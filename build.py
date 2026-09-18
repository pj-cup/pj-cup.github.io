#!/usr/bin/env python3
"""Generate docs/ (GitHub Pages site) from the latest dated CSV snapshot in csv/."""

import csv
import html
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
]


def find_latest_snapshot(csv_dir):
    candidates = [p for p in csv_dir.glob("*.csv") if SNAPSHOT_RE.match(p.name)]
    if not candidates:
        raise SystemExit(f"No snapshot CSVs (YYYYMMDD.csv) found in {csv_dir}")
    return max(candidates, key=lambda p: p.name)


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
        return "tba", "TBA", "Scheduled, not yet played"
    set_count = raw.count(",") + 1
    if set_count < 2:
        return "ongoing", raw, "Match in progress — not yet counted in standings"
    return "result", raw, None


def render_standings_table(standings):
    thead_cells = "".join(
        f'<th class="num">{label}</th>' if numeric else f"<th>{label}</th>"
        for _, label, numeric in STANDINGS_COLUMNS
    )

    body_rows = []
    for row_data in standings:
        cells = []
        for key, _, numeric in STANDINGS_COLUMNS:
            value = html.escape(row_data[key])
            cls = ' class="num"' if numeric else ""
            cells.append(f"<td{cls}>{value}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        "<table>\n"
        f"<thead><tr>{thead_cells}</tr></thead>\n"
        f"<tbody>{''.join(body_rows)}</tbody>\n"
        "</table>"
    )


def render_rules_section(standings):
    items = [s for s in standings if s["rules"]]
    if not items:
        return ""

    list_items = "".join(
        f'<li><span class="badge">{html.escape(s["rules"].replace("📌", "").strip())}</span></li>'
        for s in items
    )

    return (
        "  <section>\n"
        "    <h2>Rules</h2>\n"
        f'    <ul class="rules-list">{list_items}</ul>\n'
        "  </section>\n"
    )


def render_h2h_table(players, grid):
    header_cells = "".join(f"<th>{html.escape(p)}</th>" for p in players)

    body_rows = []
    for row_player in players:
        row_cells = [f"<th>{html.escape(row_player)}</th>"]
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


def render_page(standings_html, rules_html, h2h_html, source_path, snapshot_date):
    template = Template((TEMPLATE_DIR / "index.html.tmpl").read_text(encoding="utf-8"))
    title = "PJ Cup Season1"
    description = f"Tennis league standings and head-to-head results, updated {snapshot_date}."
    return template.substitute(
        title=title,
        description=html.escape(description),
        page_url=SITE_URL,
        image_url=f"{SITE_URL}logo.png",
        snapshot_date=snapshot_date,
        source_file=f"csv/{source_path.name}",
        standings_table=standings_html,
        rules_section=rules_html,
        h2h_table=h2h_html,
    )


def main():
    latest = find_latest_snapshot(CSV_DIR)
    print(f"Using latest snapshot: {latest.relative_to(ROOT)}")

    standings, players, grid = parse_snapshot(latest)
    snapshot_date = format_snapshot_date(latest)

    standings_html = render_standings_table(standings)
    rules_html = render_rules_section(standings)
    h2h_html = render_h2h_table(players, grid)
    page_html = render_page(standings_html, rules_html, h2h_html, latest, snapshot_date)

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(page_html, encoding="utf-8")
    (DOCS_DIR / "style.css").write_text(
        (TEMPLATE_DIR / "style.css.tmpl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (DOCS_DIR / "theme.js").write_text(
        (TEMPLATE_DIR / "theme.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    shutil.copyfile(LOGO_SOURCE, DOCS_DIR / "logo.png")

    print(
        f"Wrote {DOCS_DIR / 'index.html'}, {DOCS_DIR / 'style.css'}, "
        f"{DOCS_DIR / 'theme.js'}, {DOCS_DIR / 'logo.png'} (from {LOGO_SOURCE.relative_to(ROOT)})"
    )
    print(f"Players: {len(players)}, standings rows: {len(standings)}")


if __name__ == "__main__":
    main()
