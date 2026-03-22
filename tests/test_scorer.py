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

def test_composite_score_clamps_to_ten():
    scores  = {"crime": 10.0}
    weights = {"crime": 5}
    result  = compute_composite_score(scores, weights)
    assert result == pytest.approx(10.0, abs=0.001)
