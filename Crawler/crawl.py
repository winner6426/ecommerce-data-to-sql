import argparse
import json
import time
from datetime import date
from pathlib import Path

import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
RAW_LAKE_DIR = DATA_DIR / "raw"
DATA_DIR.mkdir(exist_ok=True)

CAT_FILE = DATA_DIR / "cat_id.json"
ID_FILE = DATA_DIR / "all_ids.json"
ID_BY_CATEGORY_FILE = DATA_DIR / "all_ids_by_category.json"
RAW_CACHE_FILE = DATA_DIR / "all_raw_data.json"

DEFAULT_REGION_V2 = 12000
DEFAULT_PAGE_START = 0
DEFAULT_PAGE_END = 3
DEFAULT_LIMIT = 20
DEFAULT_SLEEP_LIST = 1.5
DEFAULT_SLEEP_DETAIL = 0.8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Apple Silicon)",
    "Accept": "application/json",
}


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def raw_partition_file(category_id: str | int, run_date: str) -> Path:
    return RAW_LAKE_DIR / f"category_id={category_id}" / f"date={run_date}" / "listings.json"


def load_categories(category_ids: list[int] | None = None) -> list[dict]:
    payload = load_json(CAT_FILE, {})
    categories = payload.get("categories", [])
    if category_ids:
        wanted = set(category_ids)
        categories = [cat for cat in categories if cat.get("cat_id") in wanted]
    if not categories:
        raise ValueError(f"No categories found in {CAT_FILE}")
    return categories


def get_ad_ids(category_id: int, page: int, region_v2: int, limit: int) -> list[int]:
    offset = page * limit
    url = (
        "https://gateway.chotot.com/v1/public/ad-listing"
        f"?region_v2={region_v2}&cg={category_id}&o={offset}&limit={limit}"
    )
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return [ad["list_id"] for ad in response.json().get("ads", []) if "list_id" in ad]


def crawl_detail(ad_id: str) -> dict:
    url = f"https://gateway.chotot.com/v1/public/ad-listing/{ad_id}"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def collect_ids(
    categories: list[dict],
    page_start: int,
    page_end: int,
    region_v2: int,
    limit: int,
    sleep_seconds: float,
) -> dict[str, list[str]]:
    ids_by_category = load_json(ID_BY_CATEGORY_FILE, {})
    all_ids = set(str(item) for item in load_json(ID_FILE, []))
    run_ids_by_category = {}

    for category in categories:
        category_id = str(category["cat_id"])
        category_name = category.get("cat_name", category_id)
        category_ids = set(str(item) for item in ids_by_category.get(category_id, []))
        run_category_ids = set()
        print(f"[IDs] category {category_id} - {category_name}: loaded {len(category_ids)}")

        for page in range(page_start, page_end):
            try:
                ids = get_ad_ids(int(category_id), page, region_v2, limit)
            except Exception as exc:
                print(f"[IDs] category {category_id} page {page + 1} error: {exc}")
                time.sleep(sleep_seconds * 2)
                continue

            page_ids = {str(item) for item in ids}
            before = len(category_ids)
            category_ids.update(page_ids)
            run_category_ids.update(page_ids)
            all_ids.update(page_ids)
            print(
                f"[IDs] category {category_id} page {page + 1}: "
                f"+{len(category_ids) - before} (category total {len(category_ids)})"
            )
            time.sleep(sleep_seconds)

        ids_by_category[category_id] = sorted(category_ids, key=str)
        run_ids_by_category[category_id] = sorted(run_category_ids, key=str)
        save_json(ID_BY_CATEGORY_FILE, ids_by_category)
        save_json(ID_FILE, sorted(all_ids, key=str))

    return run_ids_by_category


def crawl_details(
    ids_by_category: dict[str, list[str]],
    sleep_seconds: float,
    run_date: str,
) -> dict:
    raw_cache = load_json(RAW_CACHE_FILE, {})
    print(f"[RAW] cache has {len(raw_cache)} records")

    for category_id, ids in ids_by_category.items():
        partition_file = raw_partition_file(category_id, run_date)
        partition_raw = load_json(partition_file, {})
        todo = [str(ad_id) for ad_id in ids if str(ad_id) not in partition_raw]
        print(
            f"[RAW] category {category_id}, date {run_date}: "
            f"{len(partition_raw)} in partition, {len(todo)} to write"
        )

        for index, ad_id in enumerate(todo, 1):
            if ad_id in raw_cache:
                data = raw_cache[ad_id]
            else:
                try:
                    data = crawl_detail(ad_id)
                except requests.HTTPError as exc:
                    status = exc.response.status_code if exc.response is not None else "unknown"
                    print(f"[RAW] HTTP {status} skip {ad_id}")
                    continue
                except Exception as exc:
                    print(f"[RAW] error {ad_id}: {exc}")
                    continue

                raw_cache[ad_id] = data
                time.sleep(sleep_seconds)

            partition_raw[ad_id] = data
            if index % 20 == 0:
                save_json(partition_file, partition_raw)
                save_json(RAW_CACHE_FILE, raw_cache)
                print(
                    f"[RAW] checkpoint category {category_id}: "
                    f"{index}/{len(todo)} (partition {len(partition_raw)})"
                )

        save_json(partition_file, partition_raw)
        save_json(RAW_CACHE_FILE, raw_cache)
        print(f"[RAW] saved partition: {partition_file}")

    print(f"[RAW] cache saved to {RAW_CACHE_FILE}")
    return raw_cache


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl Chotot/Nhatot listings by category.")
    parser.add_argument(
        "--categories",
        nargs="*",
        type=int,
        help="Category IDs to crawl. Omit to crawl all categories in data/cat_id.json.",
    )
    parser.add_argument("--region-v2", type=int, default=DEFAULT_REGION_V2)
    parser.add_argument("--page-start", type=int, default=DEFAULT_PAGE_START)
    parser.add_argument("--page-end", type=int, default=DEFAULT_PAGE_END)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--sleep-list", type=float, default=DEFAULT_SLEEP_LIST)
    parser.add_argument("--sleep-detail", type=float, default=DEFAULT_SLEEP_DETAIL)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--ids-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    categories = load_categories(args.categories)

    print("=" * 60)
    print("CRAWL CHOTOT/NHATOT")
    print("=" * 60)
    print(f"Categories: {', '.join(str(cat['cat_id']) for cat in categories)}")
    print(f"Pages: {args.page_start}..{args.page_end - 1}, region_v2={args.region_v2}")
    print(f"Run date: {args.run_date}")

    ids_by_category = collect_ids(
        categories=categories,
        page_start=args.page_start,
        page_end=args.page_end,
        region_v2=args.region_v2,
        limit=args.limit,
        sleep_seconds=args.sleep_list,
    )
    if not args.ids_only:
        crawl_details(ids_by_category, args.sleep_detail, args.run_date)


if __name__ == "__main__":
    main()
