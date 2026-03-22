"""
Fetches median 2BR rent per census tract from Census ACS 5-year estimates.
Variable: B25031_004E (median gross rent for 2-bedroom units).

Outputs: data/raw/rent_raw.csv  [tract_id, rent_2br_median]
"""
import os
import requests
import pandas as pd
from pipeline.config import (
    RAW_DIR, CACHE_MAX_AGE_DAYS,
    CENSUS_ACS_BASE, CENSUS_RENT_VAR,
    CA_STATE_FIPS, LA_COUNTY_FIPS,
)
from pipeline.utils.cache import is_fresh

OUT_PATH = RAW_DIR / "rent_raw.csv"


def fetch() -> None:
    if is_fresh(OUT_PATH, days=CACHE_MAX_AGE_DAYS):
        print("rent: cache fresh — skipping")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api_key = os.environ.get("CENSUS_API_KEY", "")
    params = {
        "get": f"{CENSUS_RENT_VAR},NAME",
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
    df["rent_2br_median"] = pd.to_numeric(df[CENSUS_RENT_VAR], errors="coerce")
    df.loc[df["rent_2br_median"] < 0, "rent_2br_median"] = None  # -666666666 = missing

    result = df[["tract_id", "rent_2br_median"]]
    result.to_csv(OUT_PATH, index=False)
    print(f"rent: wrote {len(result)} tracts to {OUT_PATH}")


if __name__ == "__main__":
    fetch()
