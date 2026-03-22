# OverlapMap — LA County Neighborhood Scorer

An interactive map that scores every census tract in LA County across 5 data layers. Adjust the weights with sliders and the map recolors in real time.

**Live map:** https://nayyarsan.github.io/overlapmap

---

## What it shows

| Layer | Source | Score direction |
|-------|--------|----------------|
| Crime Rate | LAPD NIBRS + LASD Calls for Service | Lower = better |
| Fire Risk | CAL FIRE FHSZ (SRA + LRA) | Lower = better |
| Environment | CalEnviroScreen 4.0 (OEHHA) | Lower burden = better |
| Schools | CDE CAASPP 2024-25 (% met/exceeded standard) | Higher = better |
| Transit / Walk | EPA Smart Location Database v3 (D4a) | Higher = better |

Each layer is normalized to 0–10 (10 = best). The composite score is computed client-side so weight changes are instant.

**Color scale:** Red (0–3.5) → Amber (3.5–6) → Yellow-green (6–8) → Green (8–10)

Popup also shows contextual data: 2BR median rent (Census ACS) and median year structures built.

---

## Data

All underlying data is public US/CA government data, published as a CC0 dataset on Kaggle:

**Dataset:** https://www.kaggle.com/datasets/nayyarsan/la-county-neighborhood-scores

Updated monthly via GitHub Actions.

---

## How it works

```
pipeline/
├── fetchers/         # Download + clean each data source
│   ├── crime.py      # LAPD NIBRS + LASD (ArcGIS REST)
│   ├── environment.py # CalEnviroScreen 4.0 (Zenodo)
│   ├── fire.py       # CAL FIRE FHSZ (ArcGIS FeatureServer)
│   ├── schools.py    # CDE CAASPP + School Directory
│   └── transit.py    # EPA Smart Location Database
├── contextual/       # Display-only layers (not scored)
│   ├── rent.py       # Census ACS B25031_004E (2BR rent)
│   └── property_age.py # Census ACS B25035_001E
├── scorer.py         # Join + normalize → TopoJSON
├── run_all.py        # Orchestrator
└── utils/
    ├── normalize.py  # Winsorize + 0-10 normalization
    └── cache.py      # Freshness checks

docs/                 # GitHub Pages static site
├── index.html
├── style.css
├── app.js            # Leaflet + live weight sliders
└── data/
    └── scored_tracts.topojson  # 2498 LA County tracts, 2.3 MB
```

**Tech stack:** Python 3.11 · pandas · geopandas · topojson | Leaflet.js 1.9.4 · Chroma.js · topojson-client | GitHub Pages · GitHub Actions

---

## Run locally

```bash
# Install dependencies
pip install -r pipeline/requirements.txt

# Download static files (TIGER/Line + EPA SLD, ~200 MB, one-time)
python -m pipeline.fetchers.static_downloads

# Run full pipeline
python -m pipeline.run_all --skip-kaggle

# Serve the map
python -m http.server 8080 --directory docs/
# Open http://localhost:8080
```

---

## Monthly refresh

A GitHub Actions workflow runs on the 1st of every month and commits updated `docs/data/scored_tracts.topojson` to this repo, which triggers a GitHub Pages redeploy.

Requires repository secrets: `KAGGLE_USERNAME`, `KAGGLE_KEY` (optional: `CENSUS_API_KEY`).

---

## License

Code: MIT
Data: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — all source data is public US/CA government data
