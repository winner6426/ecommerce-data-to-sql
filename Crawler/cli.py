from __future__ import annotations

import argparse
import sys
from datetime import date

from .client import ChototClient
from .config import (
    DEFAULT_LIMIT,
    DEFAULT_PAGE_END,
    DEFAULT_PAGE_START,
    DEFAULT_SLEEP_DETAIL,
    DEFAULT_SLEEP_LIST,
)
from .utils import load_categories
from .pipeline import collect_ids, crawl_details


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl Chotot/Nhatot listings by category.")
    parser.add_argument( 
        "--categories",
        nargs="*",
        type=int,
        help="Category IDs to crawl. Omit to crawl all categories in data/cat_id.json.",
    )
    parser.add_argument(
        "--region",
        "--regions",
        dest="region",
        type=int,
        default=None,
        help="Optional region filter. Omit to crawl listings from any region.",
    )
    parser.add_argument("--page-start", type=int, default=DEFAULT_PAGE_START)
    parser.add_argument("--page-end", type=int, default=DEFAULT_PAGE_END)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--sleep-list", type=float, default=DEFAULT_SLEEP_LIST)
    parser.add_argument("--sleep-detail", type=float, default=DEFAULT_SLEEP_DETAIL)
    parser.add_argument("--run-date", default=date.today().isoformat())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    categories = load_categories(args.categories)
    client = ChototClient()

    print("=" * 60)
    print("CRAWL CHOTOT")
    print("=" * 60)
    print(f"Categories: {', '.join(str(cat['cat_id']) for cat in categories)}")
    region_text = "any" if args.region is None else str(args.region)
    print(f"Pages: {args.page_start}..{args.page_end - 1}, region={region_text}")
    print(f"Date: {args.run_date}")

    ids_by_category = collect_ids(
        categories=categories,
        page_start=args.page_start,
        page_end=args.page_end,
        region=args.region,
        limit=args.limit,
        sleep_seconds=args.sleep_list,
        client=client,
    )
    crawl_details(ids_by_category, args.sleep_detail, args.run_date, client=client)
