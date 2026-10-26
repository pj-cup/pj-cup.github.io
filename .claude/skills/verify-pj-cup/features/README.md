# PJ Cup verification map

The maintained list of what `check.sh` proves. Read a feature file before relying on its result.

## Baseline preconditions

- Run from the repo root with Python 3 on `PATH`.
- `csv/` holds at least one `YYYYMMDD.csv` snapshot.
- `docs/` contains only generated output (never hand-edited).

## Proof and skip reporting

- Proof is the exit code plus `summary.txt` in the run's `.verify/` directory.
- A FAIL line names the log that holds the detail. Quote that log, not just the summary.
- The browser rendering (pages, player cards, compare, language switch, beta motion) is **not** covered. Don't report it as verified on the strength of this skill.

## Features

- [Snapshot consistency](./snapshot-consistency.md): `verify.py` mirror-matrix and standings reconciliation.
- [Build output](./build-output.md): `build.py` is clean and uses the latest snapshot.
- [Build idempotence](./build-idempotence.md): a second build leaves `docs/` byte-identical.
