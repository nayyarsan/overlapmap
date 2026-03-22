# OverlapMap — LA County Neighborhood Scorer
**Design Spec · 2026-03-21**

---

## 1. Purpose

OverlapMap is a personal-use tool to identify the best areas to live in LA County based on publicly available data. It produces a scored, color-coded map overlay of all LA County census tracts, combining crime, fire risk, environmental burden, school quality, and transit access into a single composite score. The user can adjust layer weights interactively in a browser with no server required.

A companion Kaggle dataset publishes all underlying raw and scored data for public reuse.

---

## 2. Goals

- Identify relatively safe, livable census tracts across LA County for relocation decisions
- Combine multiple negative and positive signals into one weighted composite score per tract
- Allow user to adjust weights and toggle layers interactively in the browser
- Publish all data as a public Kaggle dataset (open-source, no proprietary sources)
- Refresh automatically on a monthly schedule via GitHub Actions
- Host visualization as a static GitHub Pages site — zero server cost

---

## 3. Non-Goals (MVP)

- No real-time data — monthly refresh cadence only
- No user accounts, logins, or saved preferences
- No rental scraping in the public dataset (Zillow/Apartments.com data is personal-use only)
- No mobile-native app
- Does not cover areas outside LA County

---

## 4. MVP Data Layers

### 4.1 Scored Layers

| ID | Layer | Direction | Source | Granularity |
|----|-------|-----------|--------|-------------|
| N1 | Crime rate | Negative | LAPD NIBRS Offenses + LAPD NIBRS Victims datasets (data.lacity.org) + LA County Sheriff incident data (egis-lacounty.hub.arcgis.com) | Incident lat/lng → Census tract |
| N2 | Fire risk | Negative | CAL FIRE FHSZ — both SRA and LRA shapefiles (osfm.fire.ca.gov) | Polygon → Census tract |
| N3 | Environmental burden | Negative | CalEnviroScreen 4.0 (OEHHA) | Census tract (pre-scored) |
| P1 | School quality | Positive | CA Dept of Education CAASPP bulk CSV (cde.ca.gov/ds/ad/downloadabledata.asp) | School point → Census tract |
| P2 | Transit + walkability | Positive | EPA Smart Location Database v3 (static 2021, one-time download) | Census block group → Census tract |

**N1 — Crime source notes:**
- As of March 2024, LAPD migrated from legacy incident-level data to FBI NIBRS format. The legacy "Crime Data from 2020 to Present" dataset is frozen at 2024. Use the two replacement datasets: **LAPD NIBRS Offenses Dataset** and **LAPD NIBRS Victims Dataset** (both on data.lacity.org, updated bi-weekly). Rows in NIBRS are victim-level, not incident-level — deduplicate by incident number before aggregating to tract.
- LAPD covers the City of Los Angeles only. LA County Sheriff covers unincorporated areas and contract cities (including Rosemead, Compton, etc.). The `crime.py` fetcher must: (1) spatially join incidents to LAPD/LASD jurisdiction boundaries, (2) fetch LAPD NIBRS and LASD incident feeds separately, (3) merge on a common schema before aggregating to census tract. No double-counting occurs because jurisdictions are geographically exclusive.
- LASD dataset: "LA County Sheriff Department — Calls For Service" or incident-level feed from `egis-lacounty.hub.arcgis.com` (ArcGIS Feature Service).
- **Common schema for LAPD + LASD merge** — both feeds must be normalized to these minimum fields before aggregation: `incident_id` (string, for NIBRS victim-row deduplication), `latitude` (float), `longitude` (float), `incident_date` (date), `offense_category` (string, mapped to one of: violent / property / other). Only incidents with valid coordinates within LA County bounding box are included. All offense types are counted toward `crime_incidents_per_1k` — no category filtering in MVP. Gang-specific filtering is a V2 layer.

**N2 — Fire risk source notes:**
- CAL FIRE publishes two separate FHSZ shapefiles: SRA (State Responsibility Area, wildland/unincorporated) and LRA (Local Responsibility Area, incorporated cities). Using SRA alone leaves incorporated city tracts with no fire score. Both must be downloaded, merged, and used together.
- Tracts with no FHSZ designation (not in any hazard zone) are assigned `fire_hazard_class = "None"` and `fire_score = 10` (best — no designated hazard).
- Hazard class mapping for normalization: None → 10, Moderate → 7, High → 4, Very High → 0.

**P1 — School quality source notes:**
- CDE has no REST API for school scores. Data is distributed as bulk CSV downloads from the CDE Downloadable Data Files page.
- Use the **CAASPP (California Assessment of Student Performance and Progress)** results file: annual CSV, one row per school, contains "Percent Met or Exceeded" for Math and ELA by grade. Download URL pattern: `https://caaspp-elpac.ets.org/caaspp/ResearchFileList`
- Join key: CDS (County-District-School) code. Geocode each school to lat/lng using the CDE School Directory file (also a bulk CSV), then spatial-join to census tract.
- School score per tract = mean of "Percent Met or Exceeded" across all schools whose centroid falls within or within 0.5 miles of the tract centroid.
- This is a **static annual download** (not monthly-refreshable mid-year). The fetcher caches and only re-downloads when a new academic year file is available.

**P2 — Transit source notes:**
- EPA Smart Location Database v3 is a **static 2021 file** — it does not update. Treat identically to TIGER/Line boundaries: one-time download, stored in `data/static/`, never re-fetched by the monthly pipeline.
- Primary variable: `D4a` (aggregate transit service frequency, afternoon peak, per square mile). Secondary: `D3b` (street intersection density, proxy for walkability).
- Data is at Census **block group** level. Aggregate to tract by population-weighted mean.

### 4.2 Contextual Layers (popup only, not scored)

| ID | Layer | Source | Census Variable |
|----|-------|--------|----------------|
| C1 | Median 2BR rent | Census ACS 5-Year API | **B25031_004E** (2-bedroom; not _003E which is 1-bedroom) |
| C2 | Median year structure built | Census ACS 5-Year API | B25035_001E |

### 4.3 V2+ Expansion Layers (architecture supports, not in MVP)

Sex offender density, gang injunction zones, flood risk (FEMA NFHL), noise pollution (EPA), homeless density (LAHSA), parks proximity, hospital proximity.

---

## 5. Scoring Model

### 5.1 Normalization

Before normalization, each raw metric is **winsorized at the 2nd and 98th percentile** across all LA County tracts to prevent extreme outliers from compressing the rest of the distribution into a narrow band.

Each metric is then normalized to a 0–10 score:

```
Negative metric:  score = (p98 - clamp(value, p2, p98)) / (p98 - p2) × 10
Positive metric:  score = (clamp(value, p2, p98) - p2) / (p98 - p2) × 10
```

Result: 10 = best in LA County (top 2%), 0 = worst in LA County (bottom 2%), for every metric.

### 5.2 Null / Missing Value Strategy

If a layer value cannot be computed for a tract (e.g., no schools within 0.5 miles, no FHSZ designation), that layer is **excluded from that tract's composite calculation** — treated as if the user had toggled the layer off for that tract only. This prevents null values from penalizing tracts unfairly. The popup displays "N/A" for that metric.

### 5.3 Composite Score (computed client-side)

```
composite = Σ(weight_i × score_i) / Σ(active_weight_i)
```

Where `active_weight_i` is the weight for layers that are both enabled by the user AND have a non-null score for that tract.

Default weights (user-adjustable 0–10 via sliders):

| Layer | Default Weight |
|-------|---------------|
| Crime | 8 |
| Fire risk | 7 |
| Environment | 5 |
| Schools | 6 |
| Transit | 4 |

Disabling a layer (checkbox off) removes it from both numerator and denominator — weights renormalize automatically.

### 5.4 Color Gradient

| Score | Color | Meaning |
|-------|-------|---------|
| 8.0 – 10.0 | Green | Strong |
| 6.0 – 8.0 | Yellow-green | Good |
| 3.5 – 6.0 | Amber | Caution |
| 0.0 – 3.5 | Red | Avoid |

---

## 6. GeoJSON Schema

One Feature per census tract (~2,300 tracts in LA County).

**On-disk file:** `docs/data/scored_tracts.topojson` (inside the GitHub Pages-served `/docs` tree so `app.js` can fetch it at `./data/scored_tracts.topojson`).

**File size:** Uncompressed TIGER/Line-based GeoJSON for LA County is typically 25–40MB. The pipeline **must** apply polygon simplification (`shapely.simplify` with `tolerance=0.0001`) and convert to TopoJSON using the `topojson` Python package. Target output size: 3–6MB. TopoJSON is decoded client-side by `topojson-client@3` via `topojson.feature()`, which produces standard GeoJSON Features in memory.

**The JSON block below shows the decoded in-memory feature schema** (as returned by `topojson.feature()` on the client), not the on-disk TopoJSON format:

```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[...]] },
  "properties": {
    "tract_id":                "06037204900",
    "tract_name":              "Census Tract 2049, Los Angeles County",

    "crime_score":             7.2,
    "fire_score":              8.5,
    "env_score":               6.1,
    "school_score":            5.8,
    "transit_score":           9.0,

    "crime_incidents_per_1k":  18.4,
    "fire_hazard_class":       "High",
    "calenviro_score":         32.1,
    "school_avg_rating":       6.5,
    "transit_freq_peak":       12.3,

    "rent_2br_median":         1480,
    "median_year_built":       1962,

    "data_updated":            "2026-03-01"
  }
}
```

---

## 7. Repository Structure

```
overlapmap/
├── pipeline/
│   ├── fetchers/
│   │   ├── crime.py           # LAPD NIBRS + LASD → crime_raw.csv
│   │   ├── fire.py            # CAL FIRE SRA + LRA → fire_raw.csv
│   │   ├── environment.py     # CalEnviroScreen → env_raw.csv
│   │   ├── schools.py         # CDE CAASPP CSV → schools_raw.csv
│   │   └── transit.py         # EPA SLD (static) → transit_raw.csv
│   ├── contextual/
│   │   ├── rent.py            # Census ACS API → rent_raw.csv
│   │   └── property_age.py    # Census ACS API → property_age_raw.csv
│   ├── scorer.py
│   ├── run_all.py
│   ├── config.py
│   └── requirements.txt
│
├── data/
│   ├── raw/
│   │   ├── crime_raw.csv
│   │   ├── fire_raw.csv
│   │   ├── env_raw.csv
│   │   ├── schools_raw.csv
│   │   ├── transit_raw.csv
│   │   ├── rent_raw.csv
│   │   └── property_age_raw.csv
│   ├── static/                # One-time downloads, never re-fetched
│   │   ├── boundaries/        # TIGER/Line census tract shapefiles
│   │   └── epa_sld/           # EPA Smart Location Database v3
│   └── metadata.json
│
├── docs/                      # GitHub Pages root
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── data/
│       └── scored_tracts.topojson   # Pipeline output — served to browser
│
├── kaggle/
│   └── dataset-metadata.json
│
├── .github/
│   └── workflows/
│       └── monthly_refresh.yml
│
└── README.md
```

---

## 8. Frontend

**Stack:** Leaflet.js 1.9.4 + Chroma.js 3.2.0 + topojson-client 3.x + Vanilla JS. No framework, no build step.

**CDN imports:**
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/chroma-js@3.2.0/chroma.min.js"></script>
<script src="https://unpkg.com/topojson-client@3/dist/topojson-client.min.js"></script>
```

**Data fetch:** `app.js` fetches `./data/scored_tracts.topojson` on load, decodes with `topojson.feature()`, and passes to Leaflet as a GeoJSON layer.

**Layout:** Split-panel — left sidebar (weight sliders + layer toggles), right map panel.

**Sidebar controls:**
- Per-layer checkbox (enable/disable) + range slider (0–10 weight)
- Updates composite score and recolors all polygons on every `input` event (no debounce needed — pure in-memory math)

**Tract click popup shows:**
- Composite score (large, color-coded)
- Per-metric score bars (or "N/A" if null for that tract)
- Raw values: crime incidents/1k, fire hazard class, CalEnviroScreen score, avg school rating, transit frequency
- Contextual: median 2BR rent, median year built

**Mobile:** Sidebar collapses to bottom drawer, map goes full-screen.

**Hosting:** GitHub Pages, source `/docs` folder, auto-deploys on push to `main`.

---

## 9. Data Pipeline

**Language:** Python 3.11+

**Dependencies (pinned):**
```
pandas==2.2.3
geopandas==1.1.3
shapely==2.1.2
pyproj==3.7.2
requests==2.32.5
kaggle==2.0.0
topojson==1.10
```

Note: `pandas` is pinned to **2.2.3** (not 3.x). GeoPandas 1.1.x has documented breaking bugs with pandas 3.0 (`pd.concat` on GeoDataFrames, `from_wkb` with missing values). Upgrade to pandas 3.x when GeoPandas publishes a confirmed-compatible release.

**Per-fetcher contract:**
- Input: none (pulls from public source or cached file)
- Output: `data/raw/<layer>_raw.csv` with columns `[tract_id, <metric_column(s)>]` — each fetcher may output multiple columns if the layer contributes both a normalization value and a display value to the GeoJSON (e.g., `fire_raw.csv` has `[tract_id, dominant_hazard_class, hazard_score_input]`)
- Idempotent: skips download if output CSV exists and is <30 days old
- Static fetchers (EPA SLD, TIGER/Line): skip always if file exists in `data/static/` — these never refresh

**scorer.py responsibilities:**
- Joins all raw CSVs on `tract_id`
- Winsorizes each numeric metric at 2nd/98th percentile
- Normalizes each metric to 0–10
- Joins with TIGER/Line census tract polygons (spatial join)
- Simplifies polygons with `shapely.simplify(tolerance=0.0001)`
- Outputs to `docs/data/scored_tracts.topojson` via `topojson` package
- Also writes raw GeoJSON to `data/raw/` for Kaggle upload

**Census tract boundaries:** US Census TIGER/Line shapefiles — one-time download, stored in `data/static/boundaries/`.

---

## 10. GitHub Actions Workflow

```yaml
name: Monthly Data Refresh
on:
  schedule:
    - cron: '0 6 1 * *'
  workflow_dispatch:
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r pipeline/requirements.txt
      - run: python pipeline/run_all.py
        env:
          CENSUS_API_KEY: ${{ secrets.CENSUS_API_KEY }}
          KAGGLE_USERNAME: ${{ secrets.KAGGLE_USERNAME }}
          KAGGLE_KEY:      ${{ secrets.KAGGLE_KEY }}
      - name: Commit updated data
        run: |
          git config user.name "overlapmap-bot"
          git config user.email "bot@overlapmap"
          git add data/ docs/data/
          git diff --staged --quiet || git commit -m "data: monthly refresh $(date +'%Y-%m')"
          git push
```

**Required secrets (one-time GitHub repo setup):**
- `CENSUS_API_KEY` — free from api.census.gov
- `KAGGLE_USERNAME` + `KAGGLE_KEY` — from Kaggle account settings

---

## 11. Kaggle Dataset

**Name:** `la-county-neighborhood-scores`

**Contents:**
- All files in `data/raw/*.csv`
- `docs/data/scored_tracts.topojson`
- `data/metadata.json`

**License:** CC0 (Public Domain) — all sources are public government data.

**Update cadence:** Pushed automatically after each monthly pipeline run via `kaggle datasets version`.

---

## 12. Extensibility Contract

Adding a V2 layer requires exactly these 5 changes:
1. New file `pipeline/fetchers/<layer>.py` implementing the fetcher contract (input: none, output: `data/raw/<layer>_raw.csv` with `[tract_id, ...]`)
2. New normalization + join logic in `scorer.py`
3. New properties in the output TopoJSON (new score column + raw display column)
4. New slider + checkbox in `docs/index.html` sidebar
5. New entry in `docs/app.js` layer config array AND new row in the tract popup template

No other files need to change.

---

## 13. Out of Scope for MVP

- Proprietary rental data (Zillow, Apartments.com) — personal-use scraping only, not in Kaggle dataset
- User authentication or saved preferences
- Server-side computation
- Coverage outside LA County
- Mobile app
