"""
Reads EPA Smart Location Database v3 (pre-downloaded static file).
Aggregates block-group level D4a + D3b to census tract by pop-weighted mean.

Outputs: data/raw/transit_raw.csv  [tract_id, transit_freq_peak, intersection_density]
"""
import glob
import pandas as pd
import geopandas as gpd
from pipeline.config import EPA_SLD_DIR, RAW_DIR, LA_FIPS_FULL
from pipeline.utils.cache import is_static

OUT_PATH = RAW_DIR / "transit_raw.csv"

# EPA SLD column names
# NOTE: SLD v3 GDB uses uppercase column names (D4A, D3B, TotPop) while
# older CSV exports used mixed case (D4a, D3b, TOTPOP10). We detect at runtime.
_BG_COL        = "GEOID10"      # 12-digit block group FIPS (consistent across versions)
_D4A_VARIANTS  = ["D4a", "D4A"]          # transit service frequency (peak)
_D3B_VARIANTS  = ["D3b", "D3B"]          # street intersection density (walkability proxy)
_POP_VARIANTS  = ["TOTPOP10", "TotPop"]  # population for weighting


def fetch() -> None:
    # Static file — always use if present
    csv_files = glob.glob(str(EPA_SLD_DIR / "**/*.csv"), recursive=True)
    gdb_files = glob.glob(str(EPA_SLD_DIR / "**/*.gdb"), recursive=True)

    if not csv_files and not gdb_files:
        raise RuntimeError("EPA SLD not found — run static_downloads.py first")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if csv_files:
        df = pd.read_csv(csv_files[0], dtype={_BG_COL: str})
    else:
        import fiona
        layers = fiona.listlayers(gdb_files[0])
        df = gpd.read_file(gdb_files[0], layer=layers[0]).drop(columns="geometry")

    # Resolve actual column names (handle both old CSV and new GDB naming)
    def _resolve(variants: list[str]) -> str:
        for name in variants:
            if name in df.columns:
                return name
        raise KeyError(f"None of {variants} found in columns: {list(df.columns[:20])}")

    _D4A_COL = _resolve(_D4A_VARIANTS)
    _D3B_COL = _resolve(_D3B_VARIANTS)
    _POP_COL = _resolve(_POP_VARIANTS)

    # Filter to LA County: GEOID10 starts with "06037"
    df = df[df[_BG_COL].astype(str).str.startswith(LA_FIPS_FULL)].copy()

    # Build tract_id from block group FIPS (first 11 digits of 12-digit BG ID)
    df["tract_id"] = df[_BG_COL].astype(str).str[:11].str.zfill(11)

    # Replace sentinel values (-99999) with NaN
    for col in [_D4A_COL, _D3B_COL, _POP_COL]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] < 0, col] = None

    # Population-weighted mean per tract
    def pw_mean(group: pd.DataFrame, col: str) -> float | None:
        valid = group[[col, _POP_COL]].dropna()
        if valid.empty or valid[_POP_COL].sum() == 0:
            return None
        return (valid[col] * valid[_POP_COL]).sum() / valid[_POP_COL].sum()

    result = (
        df.groupby("tract_id")
        .apply(lambda g: pd.Series({
            "transit_freq_peak":    pw_mean(g, _D4A_COL),
            "intersection_density": pw_mean(g, _D3B_COL),
        }), include_groups=False)
        .reset_index()
    )

    # Tracts with no transit service get 0 frequency (not missing data — they have zero service)
    result["transit_freq_peak"] = result["transit_freq_peak"].fillna(0.0)

    result.to_csv(OUT_PATH, index=False)
    print(f"transit: wrote {len(result)} tracts to {OUT_PATH}")


if __name__ == "__main__":
    fetch()
