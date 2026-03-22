from pathlib import Path
import time


def is_fresh(path: Path, days: int = 30) -> bool:
    """Return True if file exists and was modified within `days` days."""
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < days * 86400


def is_static(path: Path) -> bool:
    """Return True if file exists (static files never re-fetch)."""
    return path.exists()
