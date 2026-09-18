#!/usr/bin/env python3
"""Verify a PJ Cup snapshot CSV: check the head-to-head grid is a consistent
mirror-matrix, and that the standings table reconciles with completed matches.

Usage: python3 verify.py csv/20260918.csv
"""

import argparse
import sys
from pathlib import Path

from build import classify_cell, parse_snapshot


def parse_sets(cell):
    return [tuple(int(x.strip()) for x in s.split("-")) for s in cell.split(",")]


def reverse_scoreline(raw):
    return ", ".join(f"{b}-{a}" for a, b in parse_sets(raw))


def check_mirror_matrix(players, grid):
    errors = []
    checked = set()
    for a in players:
        for b in players:
            if a == b:
                continue
            pair = tuple(sorted((a, b)))
            if pair in checked:
                continue
            checked.add(pair)

            ab = grid.get(a, {}).get(b, "")
            ba = grid.get(b, {}).get(a, "")
            cls_ab, _, _ = classify_cell(ab, a, b)
            cls_ba, _, _ = classify_cell(ba, b, a)

            if cls_ab != cls_ba:
                errors.append(
                    f"{a} vs {b}: cell kind mismatch ({a}->{b}={ab!r} is "
                    f"'{cls_ab}', {b}->{a}={ba!r} is '{cls_ba}')"
                )
            elif cls_ab in ("result", "ongoing"):
                expected_ba = reverse_scoreline(ab)
                if expected_ba != ba:
                    errors.append(
                        f"{a} vs {b}: '{ab}' should mirror to '{expected_ba}' "
                        f"but {b}'s cell has '{ba}'"
                    )
    return errors


def recompute_standings(players, grid):
    computed = {}
    for p in players:
        mp = w = d = l = gf = ga = 0
        for opp in players:
            if opp == p:
                continue
            raw = grid.get(p, {}).get(opp, "")
            cls, _, _ = classify_cell(raw, p, opp)
            if cls != "result":
                continue  # empty/TBA/ongoing matches aren't counted yet

            sets = parse_sets(raw)
            mp += 1
            won = sum(1 for a, b in sets if a > b)
            lost = sum(1 for a, b in sets if a < b)
            for a, b in sets:
                gf += a
                ga += b
            if won == 2:
                w += 1
            elif lost == 2:
                l += 1
            else:
                d += 1
        computed[p] = {
            "mp": mp, "w": w, "d": d, "l": l,
            "gf": gf, "ga": ga, "gd": gf - ga, "pts": 3 * w + d,
        }
    return computed


def check_standings(standings, computed):
    errors = []
    for row in standings:
        name = row["name"]
        expected = computed.get(name)
        if expected is None:
            errors.append(f"{name}: not found in head-to-head grid")
            continue
        for field in ("mp", "w", "d", "l", "gf", "ga", "gd", "pts"):
            actual = int(row[field])
            if actual != expected[field]:
                errors.append(
                    f"{name} {field}: CSV={actual} "
                    f"computed-from-completed-matches={expected[field]}"
                )
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="path to a PJ Cup snapshot CSV")
    args = parser.parse_args()

    standings, players, grid = parse_snapshot(args.csv_path)

    mirror_errors = check_mirror_matrix(players, grid)
    computed = recompute_standings(players, grid)
    standings_errors = check_standings(standings, computed)

    print(f"Checked {args.csv_path}")
    print(f"Players: {len(players)}, standings rows: {len(standings)}")

    if mirror_errors:
        print(f"\nMirror-matrix errors ({len(mirror_errors)}):")
        for err in mirror_errors:
            print(f"  - {err}")
    else:
        print("\nMirror-matrix: OK (every match mirrors correctly between both players)")

    if standings_errors:
        print(f"\nStandings reconciliation errors ({len(standings_errors)}):")
        for err in standings_errors:
            print(f"  - {err}")
    else:
        print("Standings: OK (reconciles with completed head-to-head matches)")

    if mirror_errors or standings_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
