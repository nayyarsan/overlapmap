import pandas as pd
import pytest
from pipeline.scorer import compute_composite_score, build_scores_df

def test_composite_score_basic():
    """Weighted average of available scores."""
    scores  = {"crime": 8.0, "fire": 6.0, "env": 5.0, "school": 7.0, "transit": 9.0}
    weights = {"crime": 8,   "fire": 7,   "env": 5,   "school": 6,   "transit": 4}
    result  = compute_composite_score(scores, weights)
    # (8*8 + 6*7 + 5*5 + 7*6 + 9*4) / (8+7+5+6+4) = (64+42+25+42+36)/30 = 209/30 ≈ 6.97
    assert result == pytest.approx(209 / 30, abs=0.01)

def test_composite_score_excludes_none():
    """None scores excluded from weighted average."""
    scores  = {"crime": 8.0, "fire": None, "env": 5.0, "school": None, "transit": 9.0}
    weights = {"crime": 8,   "fire": 7,    "env": 5,   "school": 6,    "transit": 4}
    result  = compute_composite_score(scores, weights)
    # Only crime(8), env(5), transit(9) contribute
    expected = (8*8 + 5*5 + 9*4) / (8 + 5 + 4)
    assert result == pytest.approx(expected, abs=0.01)

def test_composite_score_all_none_returns_none():
    scores  = {"crime": None, "fire": None}
    weights = {"crime": 8,    "fire": 7}
    assert compute_composite_score(scores, weights) is None

def test_composite_score_single_layer():
    scores  = {"crime": 10.0}
    weights = {"crime": 5}
    result  = compute_composite_score(scores, weights)
    assert result == pytest.approx(10.0, abs=0.001)

def test_build_scores_df_normalizes_columns():
    """build_scores_df adds score columns to the DataFrame."""
    df = pd.DataFrame({
        "tract_id": ["06037000100", "06037000200", "06037000300"],
        "crime_incidents_per_1k": [100.0, 50.0, None],
        "hazard_score_input": [0.0, 5.0, 10.0],
        "calenviro_score": [80.0, 40.0, 20.0],
        "school_avg_rating": [60.0, None, 80.0],
        "transit_freq_peak": [None, None, None],
    })
    result = build_scores_df(df.copy())
    assert "crime_score" in result.columns
    assert "fire_score" in result.columns
    assert "env_score" in result.columns
    assert "school_score" in result.columns
    assert "transit_score" in result.columns
    # All transit scores should be None (all-None input)
    assert result["transit_score"].isna().all()
    # Non-null scores should be in [0, 10]
    for col in ["crime_score", "fire_score", "env_score", "school_score"]:
        non_null = result[col].dropna()
        if len(non_null) > 0:
            assert (non_null >= 0).all() and (non_null <= 10).all()

def test_build_scores_df_nan_treated_as_none():
    """NaN values in input should produce None (not NaN) in score output."""
    import math
    df = pd.DataFrame({
        "tract_id": ["06037000100", "06037000200", "06037000300"],
        "crime_incidents_per_1k": [100.0, 50.0, float("nan")],
    })
    # Add only crime layer, leave others absent
    result = build_scores_df(df.copy())
    assert "crime_score" in result.columns
    crime_scores = result["crime_score"].tolist()
    # Rows 0 and 1 had valid input — they should produce valid numeric scores
    assert crime_scores[0] is not None and not math.isnan(crime_scores[0])
    assert crime_scores[1] is not None and not math.isnan(crime_scores[1])
    # Third row had NaN input — its score should be None/NaN (not a valid score)
    assert crime_scores[2] is None or math.isnan(crime_scores[2])
