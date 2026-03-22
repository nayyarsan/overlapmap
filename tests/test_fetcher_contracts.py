"""
Smoke tests: verify each fetcher's output CSV has the required columns.
Run after fetchers have been executed at least once.
"""
import pytest
import pandas as pd
from pipeline.config import RAW_DIR


def _load(name: str) -> pd.DataFrame:
    path = RAW_DIR / f"{name}_raw.csv"
    if not path.exists():
        pytest.skip(f"{path} not yet generated — run pipeline first")
    return pd.read_csv(path, dtype={"tract_id": str}, keep_default_na=False)


def test_env_raw_schema():
    df = _load("env")
    assert "tract_id" in df.columns
    assert "calenviro_score" in df.columns
    assert df["tract_id"].dtype == object  # string FIPS
    assert df["calenviro_score"].between(0, 100, inclusive="both").all()


def test_fire_raw_schema():
    df = _load("fire")
    assert "tract_id" in df.columns
    assert "dominant_hazard_class" in df.columns
    assert "hazard_score_input" in df.columns
    valid_classes = {"None", "Moderate", "High", "Very High"}
    assert set(df["dominant_hazard_class"].unique()).issubset(valid_classes)
    assert df["hazard_score_input"].between(0, 10, inclusive="both").all()


def test_transit_raw_schema():
    df = _load("transit")
    assert "tract_id" in df.columns
    assert "transit_freq_peak" in df.columns
    assert "intersection_density" in df.columns
    assert df["tract_id"].is_unique
    assert df["tract_id"].str.len().eq(11).all()
    # Convert to numeric, coerce errors to NaN, then check non-negative values
    transit_freq = pd.to_numeric(df["transit_freq_peak"], errors="coerce")
    intersection = pd.to_numeric(df["intersection_density"], errors="coerce")
    assert (transit_freq.dropna() >= 0).all()
    assert (intersection.dropna() >= 0).all()


def test_schools_raw_schema():
    df = _load("schools")
    assert "tract_id" in df.columns
    assert "school_avg_rating" in df.columns
    ratings = pd.to_numeric(df["school_avg_rating"], errors="coerce").dropna()
    assert ratings.between(0, 100, inclusive="both").all()
    assert df["tract_id"].is_unique
    assert df["tract_id"].str.len().eq(11).all()


def test_crime_raw_schema():
    df = _load("crime")
    assert "tract_id" in df.columns
    assert "crime_incidents_per_1k" in df.columns
    assert (df["crime_incidents_per_1k"] >= 0).all()
    assert df["tract_id"].is_unique
    assert df["tract_id"].str.len().eq(11).all()


def test_rent_raw_schema():
    df = _load("rent")
    assert "tract_id" in df.columns
    assert "rent_2br_median" in df.columns
    assert df["tract_id"].is_unique
    assert df["tract_id"].str.len().eq(11).all()
    rent_values = pd.to_numeric(df["rent_2br_median"], errors="coerce").dropna()
    assert (rent_values > 0).all()


def test_property_age_raw_schema():
    df = _load("property_age")
    assert "tract_id" in df.columns
    assert "median_year_built" in df.columns
    assert df["tract_id"].is_unique
    assert df["tract_id"].str.len().eq(11).all()
    year_values = pd.to_numeric(df["median_year_built"], errors="coerce").dropna()
    assert (year_values >= 1800).all()
    assert (year_values <= 2030).all()
