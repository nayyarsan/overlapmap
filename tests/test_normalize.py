import numpy as np
import pytest
from pipeline.utils.normalize import winsorize, normalize_metric

def test_winsorize_clips_outliers():
    values = list(range(100))  # 0..99
    result = winsorize(values)
    # 2nd percentile of 0..99 ≈ 1.98, 98th ≈ 97.02
    assert result[0] == pytest.approx(result[1], abs=0.1)   # 0 clipped up to p2
    assert result[-1] == pytest.approx(result[-2], abs=0.1)  # 99 clipped down to p98

def test_normalize_negative_metric_worst_is_zero():
    values = [1.0, 5.0, 10.0]
    scores = normalize_metric(values, direction="negative")
    # highest raw value → lowest score
    assert scores[2] == pytest.approx(0.0, abs=0.01)

def test_normalize_positive_metric_best_is_ten():
    values = [1.0, 5.0, 10.0]
    scores = normalize_metric(values, direction="positive")
    # highest raw value → score 10
    assert scores[2] == pytest.approx(10.0, abs=0.01)

def test_normalize_output_range():
    values = [2.0, 4.0, 6.0, 8.0, 10.0]
    scores = normalize_metric(values, direction="positive")
    assert all(0.0 <= s <= 10.0 for s in scores)

def test_normalize_null_passthrough():
    values = [1.0, None, 10.0]
    scores = normalize_metric(values, direction="positive")
    assert scores[1] is None

def test_normalize_constant_series_returns_none():
    """All same value — no spread, normalization undefined."""
    values = [5.0, 5.0, 5.0]
    scores = normalize_metric(values, direction="positive")
    assert all(s is None for s in scores)
