# Build idempotence

Running `build.py` twice in a row leaves every file in `docs/` byte-identical.

## Sub-features

- `md5-match` checks that per-file md5s of `docs/` match after the first and second builds.
- `head-diff` reports which generated files differ from HEAD (informational only).

## How to get to it (user POV)

- Any change to the build inputs, then run the check.

## Driving it with check.sh

Preconditions:

- `build.py` passed (see [Build output](./build-output.md)).

- **Rebuild.** Run `.claude/skills/verify-pj-cup/scripts/check.sh`. `summary.txt` has `PASS idempotent (N files in docs/)`.
- **Proof.** `cmp md5-1.txt md5-2.txt` shows no difference. `docs-diff.txt` lists the files the change regenerated.
- **Beta-only change.** If only `beta.*` templates or `render_beta_*` changed, `docs-diff.txt` must not list `docs/index.html` or `docs/en.html`. Check that by hand.

## Gotchas

- `docs-diff.txt` being non-empty is expected after a source change. It isn't a failure.
- Anything time- or order-dependent in the build (timestamps, set ordering) shows up here as a FAIL.
