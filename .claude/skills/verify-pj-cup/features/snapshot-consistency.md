# Snapshot consistency

A snapshot's head-to-head grid mirrors between both players, and its standings table matches the completed matches in the grid.

## Sub-features

- `mirror` checks that cell `[A][B]` is the reverse scoreline of `[B][A]`.
- `standings` checks that MP/W/D/L/GF/GA/GD/Pts reconcile with completed (two-set) cells.

## How to get to it (user POV)

- Add or edit `csv/YYYYMMDD.csv`, then run the check.

## Driving it with check.sh

Preconditions:

- The CSV exists and has both tables, separated by an all-empty row.

- **Check latest.** Run `.claude/skills/verify-pj-cup/scripts/check.sh`. `summary.txt` has `PASS verify.py`.
- **Check a specific file.** Run `.claude/skills/verify-pj-cup/scripts/check.sh csv/YYYYMMDD.csv`. Same line, for that file.
- **Proof.** `verify.log` ends with `Mirror-matrix: OK` and `Standings: OK`. On failure it lists each mismatch under `Mirror-matrix errors` or `Standings reconciliation errors`.

## Gotchas

- Single-set cells are in-progress and are excluded from standings, so a one-set cell never causes a standings mismatch.
- Empty and `TBA` cells both mean not played.
- A non-latest CSV argument doesn't change what `build.py` builds.
