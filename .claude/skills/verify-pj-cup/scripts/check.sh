#!/bin/sh
# Data + build check for the PJ Cup site. Usage: check.sh [path/to/snapshot.csv]
# The CSV argument only changes what verify.py checks; build.py always uses the latest csv/*.csv.
set -u

ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
cd "$ROOT" || exit 2

LATEST=$(ls csv/*.csv 2>/dev/null | sort | tail -n 1)
CSV=${1:-$LATEST}
OUT=".verify/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$OUT"
FAIL=0

say() { echo "$1" | tee -a "$OUT/summary.txt"; }

docs_md5() {
    find docs -type f ! -name .DS_Store | sort | while read -r f; do
        printf '%s  %s\n' "$(python3 -c 'import hashlib,sys; print(hashlib.md5(open(sys.argv[1],"rb").read()).hexdigest())' "$f")" "$f"
    done
}

say "csv: $CSV"
say "latest: $LATEST"
say "git: $(git rev-parse --short HEAD 2>/dev/null || echo none)"

if python3 verify.py "$CSV" >"$OUT/verify.log" 2>&1; then
    say "PASS verify.py"
else
    say "FAIL verify.py (see $OUT/verify.log)"
    FAIL=1
fi

if python3 build.py >"$OUT/build1.out" 2>"$OUT/build1.err"; then
    if [ -s "$OUT/build1.err" ]; then
        say "FAIL build.py wrote to stderr (see $OUT/build1.err)"
        FAIL=1
    elif ! grep -qxF "Using latest snapshot: $LATEST" "$OUT/build1.out"; then
        say "FAIL build.py did not use $LATEST (see $OUT/build1.out)"
        FAIL=1
    else
        say "PASS build.py"
    fi
else
    say "FAIL build.py exited non-zero (see $OUT/build1.err)"
    FAIL=1
fi

docs_md5 >"$OUT/md5-1.txt"
python3 build.py >"$OUT/build2.out" 2>"$OUT/build2.err"
docs_md5 >"$OUT/md5-2.txt"
if cmp -s "$OUT/md5-1.txt" "$OUT/md5-2.txt"; then
    say "PASS idempotent ($(wc -l <"$OUT/md5-1.txt" | tr -d ' ') files in docs/)"
else
    say "FAIL rebuild changed docs/ (diff $OUT/md5-1.txt $OUT/md5-2.txt)"
    FAIL=1
fi

git status --porcelain docs/ >"$OUT/docs-diff.txt" 2>/dev/null
say "info docs/ vs HEAD: $(wc -l <"$OUT/docs-diff.txt" | tr -d ' ') changed file(s)"

if [ "$FAIL" -eq 0 ]; then say "RESULT PASS"; else say "RESULT FAIL"; fi
say "evidence: $OUT"
exit "$FAIL"
