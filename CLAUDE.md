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

**Data flow:** `csv/YYYYMMDD.csv` + `assets/logo_1000.png` → `build.py` → `docs/index.html` + `docs/style.css` + `docs/theme.js` + `docs/logo.png` + `docs/beta.html` + `docs/beta.css` + `docs/beta.js`

- **`csv/YYYYMMDD.csv`** — one full snapshot per matchday. Each file is self-contained (no merging across files; the only cross-file use is the display-only rank-change indicator below); `build.py` always picks the *lexicographically latest* filename via `find_latest_snapshot()`, since `YYYYMMDD` sorts chronologically as a string. Adding a new matchday means adding a new dated file here, not editing the old one.

- **CSV format** — a single file packs two tables separated by a non-blank "blank" row (`,,,,,,,,,,,`, detected by `all(cell.strip() == "")`, not by an empty string):
  1. **Standings**: `#,SS1,MP,W,D,L,GF,GA,GD,Pts,Rules,` — `SS1` is the player-name column (legacy label), `Rules` is freeform text (often empty, sometimes an emoji + short note like `📌2 Set`).
  2. **Head-to-head grid**: header `vs,<player>,...` (players alphabetical), then one row per player with one cell per opponent. Cells are quoted (contain commas), so must be parsed with the `csv` module, never `str.split(",")`.

- **Head-to-head cell semantics** (`classify_cell()` in `build.py`) — matches are best-of-2-sets:
  - empty → not played yet (no result)
  - `TBA` → not played yet (no result); just a note that the pair plans to play. Treat it the same as empty — neither is a confirmed fixture list, and any unplayed pair may still be played
  - one set score only (e.g. `2-3`) → match **in progress**, not yet counted in standings
  - two set scores (e.g. `4-0, 4-0`) → completed, counted in standings
  - The grid is asymmetric by design: cell `[A][B]` is A's-perspective score, `[B][A]` is B's-perspective (reversed) score. Render as-is; do not dedupe or merge the two.
  - Standings (MP/W/D/L/GF/GA/GD/Pts) are taken verbatim from the CSV, not recomputed by `build.py`. Points formula, if ever needed for validation, is `3×W + 1×D`.

- **`build.py`** — stdlib only (`csv`, `pathlib`, `re`, `shutil`, `string.Template`, `html`). Reads the latest snapshot, parses both tables, renders HTML markup directly — `render_standings_table`, `render_rules_section`, `render_h2h_table` for `index.html`; `render_beta_standings`, `render_beta_h2h`, `render_beta_page` for `beta.html` — fills `templates/index.html.tmpl` / `templates/beta.html.tmpl` via `string.Template`, copies `templates/style.css.tmpl`, `theme.js`, `beta.css.tmpl` and `beta.js` into `docs/` verbatim (only the `*.html.tmpl` files are substituted), and copies the brand logo from `assets/logo_1000.png` (`LOGO_SOURCE`) to `docs/logo.png`. Both pages share `parse_snapshot`, `classify_cell`, `format_snapshot_date` and `SITE_TITLE`/`SITE_URL`. Re-running is idempotent — it never reads its own prior output.

- **Derived `Pts/MP`** (both pages) — `Pts ÷ MP` to 2 decimals (`format_pts_per_match()`, `–` when MP is 0), computed from the CSV's own `Pts`/`MP` cells. On `index.html` it is the last standings column (`render_standings_table`); on `beta.html` it is an `x.xx/MP` line under the PTS label of each card (`.ppm`, `render_beta_standings`). Every other standings value is verbatim from the CSV; this one is display-only and never feeds anything (the beta count-up still ends on the CSV points).

- **Rank-change indicator** (both pages) — `find_previous_snapshot()` picks the next-lower `YYYYMMDD.csv` than the latest, `compute_rank_moves()` diffs the CSV `#` (rank) column between the two, and `render_rank_move()` produces a `▲N` / `▼N` / `–` span (`.rank-move`). `index.html` appends it to each player's `#` cell; `beta.html` shows it as a corner badge on the rank circle (inside a `.rankcol` wrapper). Both pages get a "Rank change vs <date>" note (`$standings_note`, built once in `main()`) under the Standings heading. Display-only: standings values are still verbatim from the latest CSV. With only one snapshot, or for a player absent from the previous one, no indicator or note is rendered.

- **`assets/`** — hand-provided binary brand assets (currently just `logo_1000.png`), as opposed to `templates/`'s text sources. Not generated, not templated — if the logo changes, replace this file and rerun `build.py`.

- **`templates/`** — HTML/CSS/JS sources. `templates/index.html.tmpl` and `templates/beta.html.tmpl` use `$placeholder` substitution (title, description, snapshot/page/image URLs, snapshot date, table/board HTML blocks, etc.), including Open Graph/Twitter Card meta tags (`SITE_URL` in `build.py`) so shared links preview with the site's title, description, and logo. Because of `$` substitution, never put a literal `$` in an `*.html.tmpl`. `docs/` is 100% generated output and should never be hand-edited — always change `templates/`, `assets/`, or `build.py` and rerun.

- **`beta.html`** — an animation-heavy, dark-only restyle of the same data, published alongside (not replacing) `index.html`. It is `noindex`, isn't linked from `index.html`, and links back to the classic view.
  - **Sources:** `templates/beta.html.tmpl`, `templates/beta.css.tmpl` (tokens on `:root`, dark-only), `templates/beta.js`. Standings render as ranked cards (`<ol class="board">`); the head-to-head grid is a tinted heatmap. `render_rules_section(section_class=...)` is shared with `index.html`.
  - **Data rules unchanged:** standings values come verbatim from the CSV, the grid is rendered as-is (both mirrored cells), and empty/`TBA` are both "not played yet" (TBA only gets a dashed outline). `cell_outcome()` (win/draw/loss tint and W/D/L letter from the set scores) is display-only and never feeds standings.
  - **Progressive motion:** an inline head script adds the `js` class and removes it again after 4s if `beta.js` never boots (`data-boot` on `<html>`); all motion rules are gated on `html.js`, and disabled under `prefers-reduced-motion` and `print`. Reveal-on-scroll uses `IntersectionObserver` with an on-screen fallback after 1.5s. Animated point totals always end on the CSV value (a timeout guarantees it) — keep that guarantee if you touch the count-up.
  - **Testing:** the intro, count-up and confetti depend on `requestAnimationFrame`/timers, so headless `--virtual-time-budget` screenshots show them half-finished (and headless `--window-size` narrower than 500px still lays out at 500px wide, then crops the screenshot — emulate device metrics over CDP to test phone widths). Verify motion in a real-time browser session, e.g. Chrome DevTools Protocol with device-metrics and reduced-motion emulation.

- **Theming** (`index.html`; `beta.html` is dark-only with its own tokens in `beta.css.tmpl`) — a green "tennis court" palette (CSS custom properties in `templates/style.css.tmpl`), supporting both light and dark mode. Dark mode follows `prefers-color-scheme` by default; a manual toggle (`templates/theme.js`) overrides it via `data-theme` on `<html>` and persists the choice in `localStorage`. Variables are defined in `:root` (light), re-declared under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]` for the explicit override.

## Verification workflow

There's no automated test suite; after any change under `templates/` or `build.py`:
1. Run `python3 build.py` and check it prints the expected source snapshot and no warnings (it warns on stderr if standings and head-to-head player lists diverge).
2. Re-run it and diff `docs/` output (e.g. `md5`) to confirm the build stayed idempotent.
3. Open `docs/index.html` (and `docs/beta.html` if you touched anything it uses) in a browser to visually check the change. If you only changed beta-specific files (`beta.*` templates or `render_beta_*`), `docs/index.html` should be byte-identical before and after — check its `md5`.

After adding or editing a CSV snapshot specifically, also run `python3 verify.py csv/YYYYMMDD.csv` (see Commands) — it reuses `parse_snapshot`/`classify_cell` from `build.py` as the single source of truth for what counts as a completed match, so it stays in sync with the site's own rendering logic.
