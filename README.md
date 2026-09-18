# pj-cup.github.io

Tennis league standings and head-to-head results, published via GitHub Pages from `docs/`. Green tennis-court theme with light/dark mode support.

## Build

Add a new snapshot as `csv/YYYYMMDD.csv`, then regenerate the site:

```
python3 build.py
```

This reads the latest dated CSV in `csv/` and writes `docs/index.html`, `docs/style.css`, `docs/theme.js`, and `docs/logo.png`, plus the animated dark-mode preview `docs/beta.html` (with `docs/beta.css` and `docs/beta.js`).

To change the logo, replace `assets/logo_1000.png` and rerun the build.

## Verify

Check that a snapshot's match results and standings are consistent with each other before publishing:

```
python3 verify.py csv/YYYYMMDD.csv
```
