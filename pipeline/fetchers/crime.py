"""
Fetches crime incidents for all of LA County.
Sources:
  - LAPD NIBRS Victims Dataset (City of LA)
  - LASD Calls For Service (unincorporated LA County + contract cities)

Common schema: incident_id, latitude, longitude, incident_date, offense_category
Aggregates to census tract → crime_incidents_per_1k (raw count; scorer divides by population).

Outputs: data/raw/crime_raw.csv  [tract_id, crime_incidents_per_1k]
"""
import requests
import pandas as pd
import geopandas as gpd
from pipeline.config import (
    RAW_DIR, BOUNDARIES_DIR, CACHE_MAX_AGE_DAYS,
    LAPD_NIBRS_OFFENSES_URL,
    LASD_CFS_URL, LA_BBOX, LA_FIPS_FULL,
)
from pipeline.utils.cache import is_fresh

OUT_PATH = RAW_DIR / "crime_raw.csv"

# Socrata page size
_PAGE_SIZE = 50000
# Rolling 12-month window
_MONTHS_BACK = 12


def _fetch_socrata_all(url: str, params: dict) -> pd.DataFrame:
    """Paginate through a Socrata JSON endpoint (LAPD uses Socrata)."""
    frames = []
    offset = 0
    while True:
        p = {**params, "$limit": _PAGE_SIZE, "$offset": offset}
        resp = requests.get(url, params=p, timeout=120)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        if len(batch) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_arcgis_all(url: str, where: str = "1=1", out_fields: str = "*") -> pd.DataFrame:
    """Paginate through an ArcGIS Feature Service REST endpoint (LASD uses ArcGIS)."""
    # Resolve the FeatureServer query endpoint from the Hub discovery URL
    query_url = url.replace("/api", "") + "/FeatureServer/0/query"
    frames = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "resultOffset": offset,
            "resultRecordCount": _PAGE_SIZE,
            "f": "json",
            "returnGeometry": "true",
            "geometryType": "esriGeometryPoint",
            "outSR": "4326",
        }
        resp = requests.get(query_url, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        rows = []
        for feat in features:
            row = feat.get("attributes", {})
            geom = feat.get("geometry", {})
            row["longitude"] = geom.get("x")
            row["latitude"]  = geom.get("y")
            rows.append(row)
        frames.append(pd.DataFrame(rows))
        if len(features) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _lapd_to_common(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize LAPD NIBRS Offenses dataset to common schema."""
    # NIBRS offenses has: dr_no (incident number), date_occ, crm_cd_desc,
    # location_1_latitude, location_1_longitude (from nested location_1 column)
    # Socrata flattens nested fields: location_1.latitude → location_1_latitude in JSON response
    df = df.rename(columns={
        "dr_no":                  "incident_id",
        "date_occ":               "incident_date",
        "location_1_latitude":    "latitude",
        "location_1_longitude":   "longitude",
        "crm_cd_desc":            "offense_raw",
    })
    # Deduplicate by incident_id (multiple offense codes per incident)
    df = df.drop_duplicates(subset=["incident_id"])
    df["offense_category"] = "other"  # MVP: count all — gang filter is V2
    return df[["incident_id", "latitude", "longitude", "incident_date", "offense_category"]]


def _lasd_to_common(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize LASD Calls For Service to common schema.

    Note: _fetch_arcgis_all guarantees geometry columns are named "latitude" and "longitude".
    This function only needs to discover incident_id and incident_date field names.
    """
    # Column names vary — map best-effort for incident_id and incident_date
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "incident" in cl and "id" in cl:
            col_map[c] = "incident_id"
        elif "date" in cl:
            col_map[c] = "incident_date"
    df = df.rename(columns=col_map)
    required = ["incident_id", "latitude", "longitude", "incident_date"]
    for r in required:
        if r not in df.columns:
            df[r] = None
    df["offense_category"] = "other"
    return df[required + ["offense_category"]]


def _bbox_filter(df: pd.DataFrame) -> pd.DataFrame:
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    mask = (
        df["latitude"].between(LA_BBOX["min_lat"], LA_BBOX["max_lat"]) &
        df["longitude"].between(LA_BBOX["min_lon"], LA_BBOX["max_lon"])
    )
    return df[mask].dropna(subset=["latitude", "longitude"])


def fetch() -> None:
    if is_fresh(OUT_PATH, days=CACHE_MAX_AGE_DAYS):
        print("crime: cache fresh — skipping")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("crime: fetching LAPD NIBRS offenses...")
    lapd_raw = _fetch_socrata_all(LAPD_NIBRS_OFFENSES_URL, {
        "$select": "dr_no,date_occ,crm_cd_desc,location_1.latitude,location_1.longitude",
        "$where": "location_1 IS NOT NULL",
    })
    lapd = _lapd_to_common(lapd_raw)
    lapd = _bbox_filter(lapd)
    print(f"  LAPD: {len(lapd)} deduplicated incidents")

    print("crime: fetching LASD calls for service (ArcGIS REST)...")
    try:
        lasd_raw = _fetch_arcgis_all(
            LASD_CFS_URL,
            where="latitude IS NOT NULL AND longitude IS NOT NULL",
            out_fields="*",
        )
        lasd = _lasd_to_common(lasd_raw)
        lasd = _bbox_filter(lasd)
        print(f"  LASD: {len(lasd)} incidents")
        combined = pd.concat([lapd, lasd], ignore_index=True)
    except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
        print(f"  LASD fetch failed ({e}) — using LAPD only")
        combined = lapd

    # Spatial join to census tracts
    shp_files = list(BOUNDARIES_DIR.glob("*.shp"))
    tracts = gpd.read_file(shp_files[0]).to_crs(epsg=4326)
    tracts = tracts[tracts["GEOID"].str.startswith(LA_FIPS_FULL)].copy()
    tracts["tract_id"] = tracts["GEOID"].astype(str).str.zfill(11)

    incidents_gdf = gpd.GeoDataFrame(
        combined,
        geometry=gpd.points_from_xy(combined["longitude"], combined["latitude"]),
        crs="EPSG:4326"
    )
    joined = gpd.sjoin(incidents_gdf, tracts[["tract_id", "geometry"]], how="left", predicate="within")

    # Count incidents per tract
    counts = joined.groupby("tract_id").size().reset_index(name="incident_count")

    # Merge back to all tracts
    result = tracts[["tract_id"]].merge(counts, on="tract_id", how="left")
    result["incident_count"] = result["incident_count"].fillna(0)
    # Store raw count; scorer.py will divide by population for per-1k rate
    result = result.rename(columns={"incident_count": "crime_incidents_per_1k"})

    result.to_csv(OUT_PATH, index=False)
    print(f"crime: wrote {len(result)} tracts to {OUT_PATH}")


if __name__ == "__main__":
    fetch()
