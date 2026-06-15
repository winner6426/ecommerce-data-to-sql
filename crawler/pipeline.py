from __future__ import annotations
import time
import requests

from .client import ChototClient
from .utils import load_json, raw_partition_file, save_json


def collect_ids(
    categories: list[dict],
    page_start: int,
    page_end: int,
    region: int | None,
    limit: int,
    sleep_seconds: float,
    client: ChototClient | None = None,
) -> dict[str, list[str]]:
    client = client or ChototClient()
    run_ids_by_category: dict[str, list[str]] = {}

    for category in categories:
        category_id = str(category["cat_id"])
        category_name = category.get("cat_name", category_id)
        run_category_ids: set[str] = set()
        region_text = "any" if region is None else str(region)
        print(f"[IDs] category {category_id} - {category_name} (region={region_text})")

        for page in range(page_start, page_end):
            try:
                ids = client.get_ad_ids(int(category_id), page, region, limit)
            except Exception as exc:
                print(f"[IDs] category {category_id} page {page + 1} error: {exc}")
                time.sleep(sleep_seconds * 2)
                continue

            page_ids = {str(item) for item in ids}
            before = len(run_category_ids)
            run_category_ids.update(page_ids)
            print(
                f"[IDs] category {category_id} page {page + 1}: "
                f"+{len(run_category_ids) - before} (run total {len(run_category_ids)})"
            )
            time.sleep(sleep_seconds)

        run_ids_by_category[category_id] = sorted(run_category_ids, key=str)

    return run_ids_by_category


def crawl_details(
    ids_by_category: dict[str, list[str]],
    sleep_seconds: float,
    run_date: str,
    client: ChototClient | None = None,
) -> None:
    client = client or ChototClient()

    for category_id, ids in ids_by_category.items():
        partition_file = raw_partition_file(category_id, run_date)
        partition_raw = load_json(partition_file, {})
        todo = [str(ad_id) for ad_id in ids if str(ad_id) not in partition_raw]
        if not ids and not partition_raw: #Nếu không có id và file rỗng => skip
            print(
                f"[RAW] category {category_id}, date {run_date}: "
                "no ids, skip empty partition"
            )
            continue
        if not todo: #Nếu không có id mới thì skip
            print(
                f"[RAW] category {category_id}, date {run_date}: "
                f"{len(partition_raw)} in partition, no new ids"
            )
            continue
        print(
            f"[RAW] category {category_id}, date {run_date}: "
            f"{len(partition_raw)} in partition, {len(todo)} to write"
        )

        for index, ad_id in enumerate(todo, 1):
            try:
                data = client.crawl_detail(ad_id)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                print(f"[RAW] HTTP {status} skip {ad_id}")
                continue
            except Exception as exc:
                print(f"[RAW] error {ad_id}: {exc}")
                continue

            partition_raw[ad_id] = data
            if index % 20 == 0:
                save_json(partition_file, partition_raw)
                print(
                    f"[RAW] checkpoint category {category_id}: "
                    f"{index}/{len(todo)} (partition {len(partition_raw)})"
                )
            time.sleep(sleep_seconds)

        save_json(partition_file, partition_raw)
        print(f"[RAW] saved partition: {partition_file}")
