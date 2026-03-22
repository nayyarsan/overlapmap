"""
Main pipeline entry point.
Runs all fetchers in order, then scorer, then pushes to Kaggle.

Usage:
    python -m pipeline.run_all
    python -m pipeline.run_all --skip-kaggle  # for local testing
"""
import argparse
import sys
from pipeline.fetchers.environment  import fetch as fetch_env
from pipeline.fetchers.fire         import fetch as fetch_fire
from pipeline.fetchers.transit      import fetch as fetch_transit
from pipeline.fetchers.schools      import fetch as fetch_schools
from pipeline.fetchers.crime        import fetch as fetch_crime
from pipeline.contextual.rent       import fetch as fetch_rent
from pipeline.contextual.property_age import fetch as fetch_property_age
from pipeline.scorer                import run as run_scorer


def main(skip_kaggle: bool = False) -> None:
    steps = [
        ("environment",  fetch_env),
        ("fire",         fetch_fire),
        ("transit",      fetch_transit),
        ("schools",      fetch_schools),
        ("crime",        fetch_crime),
        ("rent",         fetch_rent),
        ("property_age", fetch_property_age),
        ("scorer",       run_scorer),
    ]

    for name, fn in steps:
        print(f"\n=== {name} ===")
        try:
            fn()
        except Exception as e:
            print(f"ERROR in {name}: {e}", file=sys.stderr)
            raise

    if not skip_kaggle:
        _push_to_kaggle()
    else:
        print("\nKaggle push skipped (--skip-kaggle)")

    print("\nPipeline complete.")


def _push_to_kaggle() -> None:
    import subprocess
    from pipeline.config import RAW_DIR
    print("\n=== kaggle push ===")
    result = subprocess.run(
        ["kaggle", "datasets", "version", "-m", "Monthly refresh", "--dir-mode", "zip"],
        cwd=str(RAW_DIR.parent.parent),  # repo root
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Kaggle push failed: {result.stderr}")
    else:
        print("Kaggle dataset updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-kaggle", action="store_true")
    args = parser.parse_args()
    main(skip_kaggle=args.skip_kaggle)
