"""
Run once to download static reference files.
These are never re-fetched by the monthly pipeline.

Usage:
    python -m pipeline.fetchers.static_downloads
"""
import zipfile
import io
import requests
from pipeline.config import (
    TIGER_URL, TIGER_PLACES_URL, EPA_SLD_URL,
    BOUNDARIES_DIR, PLACES_DIR, EPA_SLD_DIR,
)


def download_tiger_tracts() -> None:
    if any(BOUNDARIES_DIR.glob("*.shp")):
        print("TIGER/Line already present — skipping.")
        return
    print("Downloading TIGER/Line LA County census tracts...")
    BOUNDARIES_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(TIGER_URL, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(BOUNDARIES_DIR)
    print(f"  extracted to {BOUNDARIES_DIR}")


def download_epa_sld() -> None:
    if any(EPA_SLD_DIR.glob("*.gdb")) or any(EPA_SLD_DIR.glob("*.csv")):
        print("EPA SLD already present — skipping.")
        return
    print("Downloading EPA Smart Location Database v3 (~200MB)...")
    EPA_SLD_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(EPA_SLD_URL, timeout=600, stream=True)
    resp.raise_for_status()
    zip_path = EPA_SLD_DIR / "epa_sld.zip"
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(EPA_SLD_DIR)
    zip_path.unlink()
    print(f"  extracted to {EPA_SLD_DIR}")


def download_tiger_places() -> None:
    """Download CA places (cities + CDPs) for place-name labeling in popups."""
    if any(PLACES_DIR.glob("tl_2023_06_place*.shp")):
        print("TIGER/Line places already present — skipping.")
        return
    print("Downloading TIGER/Line CA places (~5MB)...")
    PLACES_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(TIGER_PLACES_URL, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(PLACES_DIR)
    print(f"  extracted to {PLACES_DIR}")


if __name__ == "__main__":
    download_tiger_tracts()
    download_tiger_places()
    download_epa_sld()
    print("Static downloads complete.")
