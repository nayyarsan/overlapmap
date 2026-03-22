from typing import Literal
import numpy as np


def winsorize(values: list[float | None], low_pct: float = 2.0, high_pct: float = 98.0) -> list[float | None]:
    """Clip values to [p_low, p_high] percentile range. Nulls pass through."""
    clean = [v for v in values if v is not None]
    if not clean:
        return values
    p_low  = np.percentile(clean, low_pct)
    p_high = np.percentile(clean, high_pct)
    return [
        None if v is None else float(np.clip(v, p_low, p_high))
        for v in values
    ]


def normalize_metric(
    values: list[float | None],
    direction: Literal["positive", "negative"],
) -> list[float | None]:
    """
    Normalize values to 0–10 after winsorizing.

    positive: higher raw → higher score (10 = best)
    negative: higher raw → lower score (0 = worst)

    Returns None for any input None, and None for all outputs if the
    series has zero spread (constant values).
    """
    winsorized = winsorize(values)
    clean = [v for v in winsorized if v is not None]
    if not clean:
        return [None] * len(values)

    p_min = min(clean)
    p_max = max(clean)
    spread = p_max - p_min
    if spread == 0:
        return [None] * len(values)

    result = []
    for v in winsorized:
        if v is None:
            result.append(None)
        elif direction == "positive":
            result.append((v - p_min) / spread * 10.0)
        else:
            result.append((p_max - v) / spread * 10.0)
    return result
