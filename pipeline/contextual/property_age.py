"""
Fetches median year structure built per census tract from Census ACS.
Variable: B25035_001E.

Outputs: data/raw/property_age_raw.csv  [tract_id, median_year_built]
"""
import os
import requests
import pandas as pd
from pipeline.config import (
    RAW_DIR, CACHE_MAX_AGE_DAYS,
    CENSUS_ACS_BASE, CENSUS_AGE_VAR,
    CA_STATE_FIPS, LA_COUNTY_FIPS,
)
from pipeline.utils.cache import is_fresh

OUT_PATH = RAW_DIR / "property_age_raw.csv"


def fetch() -> None:
    if is_fresh(OUT_PATH, days=CACHE_MAX_AGE_DAYS):
        print("property_age: cache fresh — skipping")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api_key = os.environ.get("CENSUS_API_KEY", "")
    params = {
        "get": f"{CENSUS_AGE_VAR},NAME",
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
    df["median_year_built"] = pd.to_numeric(df[CENSUS_AGE_VAR], errors="coerce")
    df.loc[df["median_year_built"] < 0, "median_year_built"] = None

    result = df[["tract_id", "median_year_built"]]
    result.to_csv(OUT_PATH, index=False)
    print(f"property_age: wrote {len(result)} tracts to {OUT_PATH}")


if __name__ == "__main__":
    fetch()
