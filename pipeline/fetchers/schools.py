"""
Fetches CDE CAASPP results + CDE School Directory.
Geocodes schools via School Directory lat/lon, spatial-joins to census tracts.
School score per tract = mean "Percent Met or Exceeded" (Math + ELA) within 0.5 miles.

Outputs: data/raw/schools_raw.csv  [tract_id, school_avg_rating]

Data notes:
  - CAASPP file uses '^' as delimiter
  - Column names: "County Code", "Type ID", "Student Group ID", "Grade", "Test ID",
    "School Code", "Percentage Standard Met and Above"
  - Type ID 7 = school-level record; Grade 13 = all grades combined
  - Student Group ID 1 = all students (only group in this file)
  - Test ID 1 = ELA, 2 = Math
  - LA County code in CAASPP = "19"
  - School Directory uses tab delimiter; CDSCode last 7 digits = CAASPP School Code
"""
import io
import zipfile
import requests
import pandas as pd
import geopandas as gpd
from pipeline.config import (
    RAW_DIR, BOUNDARIES_DIR, CACHE_MAX_AGE_DAYS,
    CAASPP_CSV_URL, CDE_SCHOOL_DIR_URL,
)
from pipeline.utils.cache import is_fresh

OUT_PATH       = RAW_DIR / "schools_raw.csv"
_CAASPP_PATH   = RAW_DIR / "_caaspp_raw.csv"
_SCHOOLS_PATH  = RAW_DIR / "_school_dir_raw.csv"

# LA County code in CDE/CAASPP system
_LA_CDE_COUNTY = "19"

# CDE School Directory actual download URL (tp=txt returns tab-delimited CSV)
_SCHOOL_DIR_DOWNLOAD_URL = (
    "https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt"
)


def _fetch_caaspp() -> pd.DataFrame:
    if is_fresh(_CAASPP_PATH, days=365):
        return pd.read_csv(_CAASPP_PATH, dtype=str)
    print("schools: downloading CAASPP results...")
    resp = requests.get(CAASPP_CSV_URL, timeout=300)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # Main data file is the .txt that is NOT the entities file
        csv_names = [
            n for n in z.namelist()
            if (n.endswith(".txt") or n.endswith(".csv"))
            and "entit" not in n.lower()
        ]
        if not csv_names:
            csv_names = [n for n in z.namelist() if n.endswith(".txt") or n.endswith(".csv")]
        with z.open(csv_names[0]) as f:
            df = pd.read_csv(f, dtype=str, encoding="latin-1", sep="^")
    df.to_csv(_CAASPP_PATH, index=False)
    return df


def _fetch_school_directory() -> pd.DataFrame:
    if is_fresh(_SCHOOLS_PATH, days=CACHE_MAX_AGE_DAYS):
        return pd.read_csv(_SCHOOLS_PATH, dtype=str)
    print("schools: downloading CDE School Directory...")
    resp = requests.get(_SCHOOL_DIR_DOWNLOAD_URL, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), dtype=str, sep="\t")
    df.to_csv(_SCHOOLS_PATH, index=False)
    return df


def fetch() -> None:
    if is_fresh(OUT_PATH, days=CACHE_MAX_AGE_DAYS):
        print("schools: cache fresh — skipping")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    caaspp = _fetch_caaspp()
    school_dir = _fetch_school_directory()

    # Strip whitespace from column names
    caaspp.columns = caaspp.columns.str.strip()
    school_dir.columns = school_dir.columns.str.strip()

    # ---- Filter CAASPP to LA County, school level, all grades, ELA + Math ----
    # Type ID 7 = school-level; Grade 13 = all grades combined
    # Test ID 1 = ELA, 2 = Math; County Code 19 = Los Angeles
    mask = (
        (caaspp["County Code"].str.strip() == _LA_CDE_COUNTY) &
        (caaspp["Type ID"].str.strip() == "7") &
        (caaspp["Grade"].str.strip() == "13") &
        (caaspp["Test ID"].str.strip().isin(["1", "2"]))
    )
    caaspp_la = caaspp[mask].copy()
    print(f"schools: {len(caaspp_la)} CAASPP rows after LA/grade/subject filter")

    caaspp_la["pct_met"] = pd.to_numeric(
        caaspp_la["Percentage Standard Met and Above"], errors="coerce"
    )
    # Average ELA + Math per school (school_code is 7-digit string)
    school_scores = (
        caaspp_la.groupby("School Code")["pct_met"]
        .mean()
        .reset_index()
    )
    school_scores.columns = ["school_code_7", "school_avg_rating"]
    school_scores["school_code_7"] = school_scores["school_code_7"].str.strip()
    print(f"schools: {len(school_scores)} unique schools with scores")

    # ---- Filter School Directory to LA County, extract last 7 digits of CDSCode ----
    dir_la = school_dir[school_dir["County"].str.strip() == "Los Angeles"].copy()
    dir_la["school_code_7"] = dir_la["CDSCode"].str.strip().str[-7:]
    print(f"schools: {len(dir_la)} LA County schools in directory")

    # ---- Merge scores with geocoordinates ----
    merged = school_scores.merge(
        dir_la[["school_code_7", "Latitude", "Longitude"]],
        on="school_code_7",
        how="inner"
    )
    print(f"schools: {len(merged)} schools after merging scores with directory")
    merged = merged.dropna(subset=["school_avg_rating"])
    merged["_lat"] = pd.to_numeric(merged["Latitude"], errors="coerce")
    merged["_lon"] = pd.to_numeric(merged["Longitude"], errors="coerce")
    merged = merged.dropna(subset=["_lat", "_lon"])
    print(f"schools: {len(merged)} schools with valid lat/lon and scores")

    # ---- Build GeoDataFrame and reproject to CA Albers (EPSG:3310) ----
    schools_gdf = gpd.GeoDataFrame(
        merged,
        geometry=gpd.points_from_xy(merged["_lon"], merged["_lat"]),
        crs="EPSG:4326"
    ).to_crs(epsg=3310)

    # ---- Load census tracts shapefile ----
    shp_files = list(BOUNDARIES_DIR.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No shapefile found in {BOUNDARIES_DIR}")
    tracts = gpd.read_file(shp_files[0]).to_crs(epsg=3310)
    tracts["tract_id"] = tracts["GEOID"].astype(str).str.zfill(11)
    print(f"schools: loaded {len(tracts)} tracts from shapefile")

    # ---- Buffer each tract by 0.5 miles = 804.67 meters ----
    tracts_buffered = tracts[["tract_id", "geometry"]].copy()
    tracts_buffered["geometry"] = tracts_buffered.geometry.buffer(804.67)

    # ---- Spatial join: find schools within buffered tracts ----
    joined = gpd.sjoin(
        schools_gdf[["school_avg_rating", "geometry"]],
        tracts_buffered[["tract_id", "geometry"]],
        how="left",
        predicate="within"
    )

    # ---- Mean school rating per tract ----
    tract_scores = (
        joined.groupby("tract_id")["school_avg_rating"]
        .mean()
        .reset_index()
    )

    # ---- Merge back to all tracts (NaN for tracts with no nearby schools) ----
    result = tracts[["tract_id"]].merge(tract_scores, on="tract_id", how="left")
    result.to_csv(OUT_PATH, index=False)
    non_null = result["school_avg_rating"].notna().sum()
    print(f"schools: wrote {len(result)} tracts to {OUT_PATH}")
    print(f"schools: {non_null} tracts have school scores, "
          f"{len(result) - non_null} tracts have no nearby schools")


if __name__ == "__main__":
    fetch()
