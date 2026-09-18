# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static GitHub Pages site publishing standings and head-to-head results for a tennis league ("PJ Cup"). There is no server and no client-side data fetching — `docs/` is a fully pre-rendered static site regenerated from CSV data by a Python build script.

## Commands

Regenerate the site after adding or editing a CSV snapshot:

```
python3 build.py
```

Check that a snapshot's head-to-head grid and standings table are internally consistent (mirror-matrix + standings reconciliation) before trusting it:

```
python3 verify.py csv/YYYYMMDD.csv
```

Exits non-zero if it finds a mismatch. No dependencies, no install step, no test suite, no linter — both scripts use only the Python standard library.

## Architecture

**Data flow:** `csv/YYYYMMDD.csv` + `assets/logo_1000.png` → `build.py` → `docs/index.html` + `docs/style.css` + `docs/theme.js` + `docs/logo.png`

- **`csv/YYYYMMDD.csv`** — one full snapshot per matchday. Each file is self-contained (no diffing/merging across files); `build.py` always picks the *lexicographically latest* filename via `find_latest_snapshot()`, since `YYYYMMDD` sorts chronologically as a string. Adding a new matchday means adding a new dated file here, not editing the old one.

- **CSV format** — a single file packs two tables separated by a non-blank "blank" row (`,,,,,,,,,,,`, detected by `all(cell.strip() == "")`, not by an empty string):
  1. **Standings**: `#,SS1,MP,W,D,L,GF,GA,GD,Pts,Rules,` — `SS1` is the player-name column (legacy label), `Rules` is freeform text (often empty, sometimes an emoji + short note like `📌2 Set`).
  2. **Head-to-head grid**: header `vs,<player>,...` (players alphabetical), then one row per player with one cell per opponent. Cells are quoted (contain commas), so must be parsed with the `csv` module, never `str.split(",")`.

- **Head-to-head cell semantics** (`classify_cell()` in `build.py`) — matches are best-of-2-sets:
  - empty → not scheduled
  - `TBA` → scheduled, not played
  - one set score only (e.g. `2-3`) → match **in progress**, not yet counted in standings
  - two set scores (e.g. `4-0, 4-0`) → completed, counted in standings
  - The grid is asymmetric by design: cell `[A][B]` is A's-perspective score, `[B][A]` is B's-perspective (reversed) score. Render as-is; do not dedupe or merge the two.
  - Standings (MP/W/D/L/GF/GA/GD/Pts) are taken verbatim from the CSV, not recomputed by `build.py`. Points formula, if ever needed for validation, is `3×W + 1×D`.

- **`build.py`** — stdlib only (`csv`, `pathlib`, `re`, `shutil`, `string.Template`, `html`). Reads the latest snapshot, parses both tables, renders HTML table markup directly (`render_standings_table`, `render_rules_section`, `render_h2h_table`), fills `templates/index.html.tmpl` via `string.Template`, copies `templates/style.css.tmpl` / `templates/theme.js` into `docs/`, and copies the brand logo from `assets/logo_1000.png` (`LOGO_SOURCE`) to `docs/logo.png`. Re-running is idempotent — it never reads its own prior output.

- **`assets/`** — hand-provided binary brand assets (currently just `logo_1000.png`), as opposed to `templates/`'s text sources. Not generated, not templated — if the logo changes, replace this file and rerun `build.py`.

- **`templates/`** — HTML/CSS/JS sources. `templates/index.html.tmpl` uses `$placeholder` substitution (title, description, snapshot/page/image URLs, snapshot date, table HTML blocks, etc.), including Open Graph/Twitter Card meta tags (`SITE_URL` in `build.py`) so shared links preview with the site's title, description, and logo. `docs/` is 100% generated output and should never be hand-edited — always change `templates/`, `assets/`, or `build.py` and rerun.

- **Theming** — a green "tennis court" palette (CSS custom properties in `templates/style.css.tmpl`), supporting both light and dark mode. Dark mode follows `prefers-color-scheme` by default; a manual toggle (`templates/theme.js`) overrides it via `data-theme` on `<html>` and persists the choice in `localStorage`. Variables are defined in `:root` (light), re-declared under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]` for the explicit override.

## Verification workflow

There's no automated test suite; after any change under `templates/` or `build.py`:
1. Run `python3 build.py` and check it prints the expected source snapshot and no warnings (it warns on stderr if standings and head-to-head player lists diverge).
2. Re-run it and diff `docs/` output (e.g. `md5`) to confirm the build stayed idempotent.
3. Open `docs/index.html` in a browser to visually check the change.

After adding or editing a CSV snapshot specifically, also run `python3 verify.py csv/YYYYMMDD.csv` (see Commands) — it reuses `parse_snapshot`/`classify_cell` from `build.py` as the single source of truth for what counts as a completed match, so it stays in sync with the site's own rendering logic.
