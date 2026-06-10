import argparse
from pathlib import Path
import sys


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from preprocessor.pipeline import run_pipeline
else:
    from .pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess raw lakehouse partitions.")
    parser.add_argument(
        "--dates",
        nargs="+",
        help="Process only these partition dates, for example: --dates 2026-06-08 2026-06-09.",
    )
    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Process all raw partition dates. Default is latest date per category.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(dates=args.dates, all_dates=args.all_dates)
