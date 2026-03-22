"""
Fetches CAL FIRE Fire Hazard Severity Zones (FHSZ) for LA County.
Downloads both SRA (2024) and LRA (2025) layers from ArcGIS FeatureServer,
merges them, spatial-joins to census tracts.

Source layers are statewide CA with small feature counts (SRA ~295, LRA ~31);
no spatial pre-filter needed — overlay clips to LA County automatically.

Outputs: data/raw/fire_raw.csv  [tract_id, dominant_hazard_class, hazard_score_input]
"""
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from pipeline.config import (
    RAW_DIR, BOUNDARIES_DIR, CACHE_MAX_AGE_DAYS,
    CALFIRE_SRA_URL, CALFIRE_LRA_URL,
)
from pipeline.utils.cache import is_fresh

OUT_PATH = RAW_DIR / "fire_raw.csv"

# Direct score mapping (spec §4.1 N2): None→10, Moderate→7, High→4, Very High→0
HAZARD_SCORE = {"None": 10.0, "Moderate": 7.0, "High": 4.0, "Very High": 0.0}

# ArcGIS page size
PAGE_SIZE = 1000


def _fetch_arcgis_layer(base_url: str, label: str) -> gpd.GeoDataFrame:
    """
    Download all features from an ArcGIS FeatureServer layer.
    Requests output in EPSG:4326.  Uses offset pagination.
    """
    query_url = f"{base_url}/query"
    params_base = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": PAGE_SIZE,
    }

    features = []
    offset = 0
    while True:
        params = {**params_base, "resultOffset": offset}
        resp = requests.get(query_url, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise RuntimeError(f"{label} ArcGIS error: {data['error']}")

        batch = data.get("features", [])
        features.extend(batch)

        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    print(f"    {label}: downloaded {len(features)} total features")
    if not features:
        raise RuntimeError(f"{label}: no features returned from FeatureServer")

    geom_list = [shape(f["geometry"]) for f in features]
    props_list = [f.get("properties", {}) for f in features]
    gdf = gpd.GeoDataFrame(props_list, geometry=geom_list, crs="EPSG:4326")
    return gdf


def _standardize(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    """Normalise hazard class column to canonical names.

    Tries HAZ_CLASS first (LACoFD layers), then FHSZ_Description (statewide layers).
    """
    gdf = gdf.copy()

    # Determine which column to use
    if "HAZ_CLASS" in gdf.columns:
        raw = gdf["HAZ_CLASS"].astype(str).str.strip().str.title()
    elif "FHSZ_Description" in gdf.columns:
        raw = gdf["FHSZ_Description"].astype(str).str.strip().str.title()
    else:
        print(f"  {label} available columns: {gdf.columns.tolist()}")
        raise RuntimeError(
            f"{label}: neither 'HAZ_CLASS' nor 'FHSZ_Description' found. "
            f"Columns: {gdf.columns.tolist()}"
        )

    mapping = {
        "Very High": "Very High",
        "High": "High",
        "Moderate": "Moderate",
        "None": "None",
        "Nan": "None",
    }
    gdf["HAZ_CLASS"] = raw.map(mapping).fillna("None")
    return gdf[["HAZ_CLASS", "geometry"]]


def fetch() -> None:
    if is_fresh(OUT_PATH, days=CACHE_MAX_AGE_DAYS):
        print("fire: cache fresh — skipping download")
        return

    print("fire: downloading CAL FIRE FHSZ SRA + LRA from ArcGIS FeatureServer...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Load TIGER/Line census tracts (statewide CA — filter to LA County)
    shp_files = list(BOUNDARIES_DIR.glob("*.shp"))
    if not shp_files:
        raise RuntimeError("TIGER/Line boundaries not found — run static_downloads.py first")
    tracts = gpd.read_file(shp_files[0]).to_crs(epsg=4326)
    tracts = tracts[tracts["GEOID"].str.startswith("06037")].copy()
    tracts["tract_id"] = tracts["GEOID"].astype(str).str.zfill(11)
    print(f"fire: loaded {len(tracts)} LA County tracts")

    gdfs = []
    for label, url in [("SRA", CALFIRE_SRA_URL), ("LRA", CALFIRE_LRA_URL)]:
        try:
            gdf = _standardize(_fetch_arcgis_layer(url, label), label)
            gdfs.append(gdf)
            print(f"  {label} standardized: {len(gdf)} features")
        except Exception as e:
            print(f"  WARNING: {label} download failed ({e}) — skipping")

    if not gdfs:
        raise RuntimeError("Both SRA and LRA downloads failed")

    fhsz_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
    print(f"fire: combined FHSZ features: {len(fhsz_gdf)}")

    # Spatial overlay: intersect tracts with FHSZ polygons
    print("fire: computing spatial overlay (this may take a minute)...")
    joined = gpd.overlay(tracts[["tract_id", "geometry"]], fhsz_gdf, how="intersection")
    joined["area"] = joined.geometry.to_crs(epsg=3310).area

    # For each tract, pick the FHSZ class with the largest intersection area
    idx_max = joined.groupby("tract_id")["area"].idxmax()
    dominant = (
        joined.loc[idx_max, ["tract_id", "HAZ_CLASS"]]
        .rename(columns={"HAZ_CLASS": "dominant_hazard_class"})
        .reset_index(drop=True)
    )

    # Tracts with no FHSZ intersection → "None"
    result = tracts[["tract_id"]].merge(dominant, on="tract_id", how="left")
    result["dominant_hazard_class"] = result["dominant_hazard_class"].fillna("None")
    result["hazard_score_input"] = result["dominant_hazard_class"].map(HAZARD_SCORE)

    result[["tract_id", "dominant_hazard_class", "hazard_score_input"]].to_csv(
        OUT_PATH, index=False
    )
    print(f"fire: wrote {len(result)} tracts to {OUT_PATH}")

    # Print distribution
    dist = result["dominant_hazard_class"].value_counts()
    print("fire: hazard class distribution:")
    for cls, count in dist.items():
        print(f"  {cls}: {count}")


if __name__ == "__main__":
    fetch()
