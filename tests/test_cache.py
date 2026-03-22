import time
from pathlib import Path
import tempfile
import pytest
from pipeline.utils.cache import is_fresh, is_static

def test_is_fresh_new_file_returns_true():
    with tempfile.NamedTemporaryFile() as f:
        assert is_fresh(Path(f.name), days=30) is True

def test_is_fresh_old_file_returns_false():
    with tempfile.NamedTemporaryFile() as f:
        path = Path(f.name)
        # backdate mtime by 31 days
        old_time = time.time() - (31 * 86400)
        import os; os.utime(path, (old_time, old_time))
        assert is_fresh(path, days=30) is False

def test_is_fresh_missing_file_returns_false():
    assert is_fresh(Path("/nonexistent/file.csv"), days=30) is False

def test_is_static_returns_true_for_existing_file():
    with tempfile.NamedTemporaryFile() as f:
        assert is_static(Path(f.name)) is True

def test_is_static_returns_false_for_missing_file():
    assert is_static(Path("/nonexistent/file.zip")) is False
