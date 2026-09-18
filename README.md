# pj-cup.github.io

Tennis league standings and head-to-head results, published via GitHub Pages from `docs/`.

## Build

Add a new snapshot as `csv/YYYYMMDD.csv`, then regenerate the site:

```
python3 build.py
```

This reads the latest dated CSV in `csv/` and writes `docs/index.html` + `docs/style.css`.
