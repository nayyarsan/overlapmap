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
