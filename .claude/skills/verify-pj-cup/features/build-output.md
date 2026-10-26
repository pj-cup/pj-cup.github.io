# Build output

`build.py` regenerates `docs/` from the latest snapshot without warnings.

## Sub-features

- `exit` checks that `build.py` exits 0.
- `no-warnings` checks that stderr is empty (it warns when the standings and grid player lists diverge).
- `latest` checks that stdout names the lexicographically latest `csv/*.csv`.

## How to get to it (user POV)

- Change `templates/`, `assets/`, `build.py` or a CSV, then run the check.

## Driving it with check.sh

Preconditions:

- The doctor command in SKILL.md passes.

- **Build.** Run `.claude/skills/verify-pj-cup/scripts/check.sh`. `summary.txt` has `PASS build.py`.
- **Proof.** `build1.out` contains `Using latest snapshot: csv/<latest>.csv` and a `Wrote ...` line, and `build1.err` is empty.

## Gotchas

- A Python traceback goes to stderr, so it shows up as `FAIL build.py exited non-zero`. Read `build1.err`.
- Passing the build doesn't mean the pages look right. The browser check is still manual.
