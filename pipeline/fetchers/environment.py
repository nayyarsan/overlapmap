"""
Fetches CalEnviroScreen 4.0 data from OEHHA.
Outputs: data/raw/env_raw.csv  [tract_id, calenviro_score]
"""
import io
import zipfile
import requests
import pandas as pd
from pipeline.config import RAW_DIR, CACHE_MAX_AGE_DAYS, LA_FIPS_FULL, CALENVIRO_URL
from pipeline.utils.cache import is_fresh

OUT_PATH = RAW_DIR / "env_raw.csv"

# Column names in the CalEnviroScreen spreadsheet
_SCORE_COL    = "CES 4.0 Score"
_TRACT_COL    = "Census Tract"
_COUNTY_COL   = "California County"


def fetch() -> None:
    if is_fresh(OUT_PATH, days=CACHE_MAX_AGE_DAYS):
        print("env: cache fresh — skipping download")
        return

    print("env: downloading CalEnviroScreen 4.0...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    resp = requests.get(CALENVIRO_URL, timeout=120)
    resp.raise_for_status()

    # Zip contains an Excel file (and PDF data dictionary)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        xlsx_names = [n for n in z.namelist() if n.endswith(".xlsx")]
        if not xlsx_names:
            raise RuntimeError("No XLSX found in CalEnviroScreen zip")
        with z.open(xlsx_names[0]) as f:
            df = pd.read_excel(f, sheet_name="CES4.0FINAL_results")

    # Filter to LA County only
    df = df[df[_COUNTY_COL].str.strip().str.upper() == "LOS ANGELES"].copy()

    # Build 11-digit FIPS tract ID: state(06) + county(037) + tract(6 digits)
    df["tract_id"] = (
        df[_TRACT_COL]
        .astype(str)
        .str.strip()
        .str.zfill(11)
    )

    # Keep only the composite score and tract ID
    result = df[["tract_id", _SCORE_COL]].copy()
    result = result.rename(columns={_SCORE_COL: "calenviro_score"})
    result = result.dropna(subset=["calenviro_score"])
    result["calenviro_score"] = pd.to_numeric(result["calenviro_score"], errors="coerce")
    result = result.dropna(subset=["calenviro_score"])
    result["tract_id"] = result["tract_id"].astype(str)

    result.to_csv(OUT_PATH, index=False)
    print(f"env: wrote {len(result)} tracts to {OUT_PATH}")


if __name__ == "__main__":
    fetch()
