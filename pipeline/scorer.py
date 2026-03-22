"""
Joins all raw CSVs + TIGER/Line geometry.
Normalizes each metric to 0–10.
Computes pre-built composite scores (for reference) and writes full TopoJSON.

The composite score is intentionally recomputed client-side in the browser
so the user can adjust weights interactively. scorer.py stores only the
per-layer 0–10 scores plus raw display values.

Outputs:
  docs/data/scored_tracts.topojson   — served by GitHub Pages
  data/raw/scored_tracts.geojson     — uploaded to Kaggle
"""
import json
import os
import requests
import pandas as pd
import geopandas as gpd
import topojson as tp
from datetime import date
from pipeline.config import (
    RAW_DIR, BOUNDARIES_DIR, PLACES_DIR, DOCS_DATA_DIR, GEOJSON_OUT,
    TOPOJSON_OUT, METADATA_PATH,
    CENSUS_ACS_BASE, CA_STATE_FIPS, LA_COUNTY_FIPS, LA_FIPS_FULL,
)
from pipeline.utils.normalize import normalize_metric

# Default weights (stored for reference; browser recomputes interactively)
DEFAULT_WEIGHTS = {
    "crime":   8,
    "fire":    7,
    "env":     5,
    "school":  6,
    "transit": 4,
}

# Layer definitions: column to normalize, direction, display column
LAYER_CONFIG = {
    "crime":   {"norm_col": "crime_incidents_per_1k", "direction": "negative", "score_col": "crime_score",   "display_col": "crime_incidents_per_1k"},
    "fire":    {"norm_col": "hazard_score_input",     "direction": "positive", "score_col": "fire_score",    "display_col": "dominant_hazard_class"},
    "env":     {"norm_col": "calenviro_score",        "direction": "negative", "score_col": "env_score",     "display_col": "calenviro_score"},
    "school":  {"norm_col": "school_avg_rating",      "direction": "positive", "score_col": "school_score",  "display_col": "school_avg_rating"},
    "transit": {"norm_col": "transit_freq_peak",      "direction": "positive", "score_col": "transit_score", "display_col": "transit_freq_peak"},
}


def compute_composite_score(
    scores: dict[str, float | None],
    weights: dict[str, int],
) -> float | None:
    """Weighted average of non-null scores. Returns None if all are null."""
    total_weight = 0
    total = 0.0
    for layer, score in scores.items():
        if score is not None:
            w = weights.get(layer, 0)
            total += w * score
            total_weight += w
    if total_weight == 0:
        return None
    return total / total_weight


def build_scores_df(merged: pd.DataFrame) -> pd.DataFrame:
    """Normalize all layers and return DataFrame with score columns added."""
    for layer, cfg in LAYER_CONFIG.items():
        col = cfg["norm_col"]
        if col not in merged.columns:
            merged[cfg["score_col"]] = None
            continue
        # Convert pandas NaN to Python None — normalize_metric uses `is not None` guard
        series = merged[col]
        values = [None if pd.isna(v) else v for v in series.tolist()]
        scores = normalize_metric(values, direction=cfg["direction"])
        merged[cfg["score_col"]] = scores
    return merged


def _fetch_tract_population() -> pd.DataFrame:
    """Fetch total population per tract from Census ACS for per-1k crime calculation."""
    api_key = os.environ.get("CENSUS_API_KEY", "")
    params = {
        "get": "B01003_001E,NAME",
        "for": "tract:*",
        "in": f"state:{CA_STATE_FIPS} county:{LA_COUNTY_FIPS}",
    }
    if api_key:
        params["key"] = api_key
    resp = requests.get(CENSUS_ACS_BASE, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["tract_id"] = (
        df["state"].str.zfill(2) +
        df["county"].str.zfill(3) +
        df["tract"].str.zfill(6)
    )
    df["population"] = pd.to_numeric(df["B01003_001E"], errors="coerce")
    df.loc[df["population"] < 0, "population"] = None
    return df[["tract_id", "population"]]


def _join_place_names(tracts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Spatial join tract centroids to TIGER Places → place_name column.

    Incorporated cities and CDPs get their official name (e.g. "Pasadena").
    Tracts whose centroid falls outside any named place get "Unincorporated".
    """
    place_files = list(PLACES_DIR.glob("tl_2023_06_place*.shp"))
    if not place_files:
        print("  WARNING: TIGER places not found — place_name will be empty")
        tracts["place_name"] = None
        return tracts

    places = gpd.read_file(place_files[0]).to_crs(epsg=4326)[["NAME", "geometry"]]

    # Use tract centroids for the join (faster and avoids edge ambiguity)
    # Project to CA Albers (EPSG:3310) for accurate centroid, then back to WGS84
    centroids_geom = tracts.to_crs(epsg=3310).geometry.centroid.to_crs(epsg=4326)
    centroids_gdf = gpd.GeoDataFrame(
        {"tract_id": tracts["tract_id"].values},
        geometry=centroids_geom.values,
        crs=tracts.crs,
    )

    joined = gpd.sjoin(
        centroids_gdf,
        places,
        how="left",
        predicate="within",
    )
    # Drop duplicate tract_ids if a centroid hit multiple place polygons
    joined = joined.drop_duplicates(subset="tract_id")

    name_map = joined.set_index("tract_id")["NAME"]
    tracts["place_name"] = tracts["tract_id"].map(name_map).fillna("Unincorporated")
    return tracts


def run() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load TIGER/Line census tracts — filter to LA County
    shp_files = list(BOUNDARIES_DIR.glob("tl_*_tract*.shp"))
    if not shp_files:
        raise RuntimeError("TIGER/Line not found — run static_downloads.py first")
    tracts = gpd.read_file(shp_files[0]).to_crs(epsg=4326)
    tracts["tract_id"] = tracts["GEOID"].astype(str).str.zfill(11)
    tracts = tracts[tracts["GEOID"].str.startswith(LA_FIPS_FULL)].copy()
    tracts["tract_name"] = tracts["NAMELSAD"].astype(str) + ", Los Angeles County"
    tracts = _join_place_names(tracts)
    merged = tracts[["tract_id", "tract_name", "place_name", "geometry"]].copy()

    # 2. Load population for per-1k crime rate
    pop = _fetch_tract_population()
    merged = merged.merge(pop, on="tract_id", how="left")

    # 3. Load and join each raw CSV
    csv_files = {
        "crime":        RAW_DIR / "crime_raw.csv",
        "fire":         RAW_DIR / "fire_raw.csv",
        "env":          RAW_DIR / "env_raw.csv",
        "school":       RAW_DIR / "schools_raw.csv",
        "transit":      RAW_DIR / "transit_raw.csv",
        "rent":         RAW_DIR / "rent_raw.csv",
        "property_age": RAW_DIR / "property_age_raw.csv",
    }
    for name, path in csv_files.items():
        if not path.exists():
            print(f"  WARNING: {path} missing — layer will be null")
            continue
        df = pd.read_csv(path, dtype={"tract_id": str})
        df["tract_id"] = df["tract_id"].str.zfill(11)
        merged = merged.merge(df, on="tract_id", how="left")

    # 4. Compute per-1k crime rate
    if "crime_incidents_per_1k" in merged.columns and "population" in merged.columns:
        merged["crime_incidents_per_1k"] = (
            merged["crime_incidents_per_1k"] /
            merged["population"].clip(lower=1) * 1000
        )

    # 5. Normalize all layers
    merged = build_scores_df(merged)

    # 6. Assemble final properties
    cols_needed = [
        "tract_id", "tract_name", "place_name", "geometry",
        "crime_score", "fire_score", "env_score", "school_score", "transit_score",
        "crime_incidents_per_1k", "dominant_hazard_class", "calenviro_score",
        "school_avg_rating", "transit_freq_peak",
        "rent_2br_median", "median_year_built",
    ]
    # Only include columns that exist
    cols_present = [c for c in cols_needed if c in merged.columns]
    output = merged[cols_present].copy()

    # Fill display-only columns with sensible defaults
    if "dominant_hazard_class" not in output.columns:
        output["dominant_hazard_class"] = None

    output["data_updated"] = str(date.today())

    # Replace any remaining pandas NaN with None so JSON output stays valid
    # (topojson serializes float NaN as the bare token NaN, which is invalid JSON)
    for c in output.columns:
        if c == "geometry":
            continue
        output[c] = output[c].where(output[c].notna(), other=None)

    # 7. Simplify polygons
    output["geometry"] = output["geometry"].simplify(tolerance=0.0001, preserve_topology=True)

    # 8. Write GeoJSON for Kaggle
    output.to_file(GEOJSON_OUT, driver="GeoJSON")
    print(f"scorer: wrote GeoJSON to {GEOJSON_OUT}")

    # 9. Convert to TopoJSON and write for GitHub Pages
    topo = tp.Topology(output, prequantize=False)
    topo_json = topo.to_json()
    # topojson serializes float NaN as bare NaN (invalid JSON); replace with null
    import re as _re
    topo_json = _re.sub(r'\bNaN\b', 'null', topo_json)
    with open(TOPOJSON_OUT, "w") as f:
        f.write(topo_json)
    size_mb = TOPOJSON_OUT.stat().st_size / 1_000_000
    print(f"scorer: wrote TopoJSON to {TOPOJSON_OUT} ({size_mb:.1f} MB)")

    # 10. Update metadata.json
    metadata = json.loads(METADATA_PATH.read_text())
    metadata["last_updated"] = str(date.today())
    METADATA_PATH.write_text(json.dumps(metadata, indent=2))
    print("scorer: updated metadata.json")


if __name__ == "__main__":
    run()
