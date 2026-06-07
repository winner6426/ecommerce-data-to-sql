import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .config import CLEAN_LAKE_DIR, LEGACY_RAW_FILE, RAW_LAKE_DIR
from .utils import clean_text, root_category_id, to_int


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def raw_partition_file(category_id: int | str, partition_date: str) -> Path:
    return RAW_LAKE_DIR / f"category_id={category_id}" / f"date={partition_date}" / "listings.json"


def clean_partition_dir(category_id: Any, partition_date: Any) -> Path:
    category_value = int(category_id) if pd.notna(category_id) else "unknown"
    date_value = clean_text(partition_date) or date.today().isoformat()
    return CLEAN_LAKE_DIR / f"category_id={category_value}" / f"date={date_value}"


def parse_partition_value(path: Path, prefix: str) -> str | None:
    for part in path.parts:
        if part.startswith(prefix):
            return part.split("=", 1)[1]
    return None


def has_raw_lakehouse() -> bool:
    return any(RAW_LAKE_DIR.glob("category_id=*/date=*/listings.json"))


def migrate_legacy_raw_to_lakehouse(run_date: str | None = None) -> None:
    if has_raw_lakehouse():
        return

    legacy_raw = load_json(LEGACY_RAW_FILE, {})
    if not legacy_raw:
        return

    partition_date = run_date or date.today().isoformat()
    partitions: dict[str, dict] = {}

    for raw_key, payload in legacy_raw.items():
        ad = payload.get("ad", {}) if isinstance(payload, dict) else {}
        category_id = root_category_id(to_int(ad.get("category"))) or "unknown"
        list_id = str(ad.get("list_id") or raw_key)
        partitions.setdefault(str(category_id), {})[list_id] = payload

    for category_id, partition_payload in partitions.items():
        save_json(raw_partition_file(category_id, partition_date), partition_payload)


def load_raw_records() -> list[dict]:
    records_by_list_id = {}

    legacy_raw = load_json(LEGACY_RAW_FILE, {})
    for raw_key, payload in legacy_raw.items():
        ad = payload.get("ad", {}) if isinstance(payload, dict) else {}
        list_id = str(ad.get("list_id") or raw_key)
        category_id = root_category_id(to_int(ad.get("category")))
        records_by_list_id[list_id] = {
            "raw_key": raw_key,
            "payload": payload,
            "partition_category_id": category_id,
            "partition_date": date.today().isoformat(),
            "source_file": str(LEGACY_RAW_FILE),
        }

    for path in RAW_LAKE_DIR.glob("category_id=*/date=*/listings.json"):
        partition_category_id = to_int(parse_partition_value(path, "category_id="))
        partition_date = parse_partition_value(path, "date=") or date.today().isoformat()
        partition_raw = load_json(path, {})

        for raw_key, payload in partition_raw.items():
            ad = payload.get("ad", {}) if isinstance(payload, dict) else {}
            list_id = str(ad.get("list_id") or raw_key)
            records_by_list_id[list_id] = {
                "raw_key": raw_key,
                "payload": payload,
                "partition_category_id": partition_category_id,
                "partition_date": partition_date,
                "source_file": str(path),
            }

    return list(records_by_list_id.values())


def write_clean_lakehouse(
    listings_df: pd.DataFrame,
    attributes_df: pd.DataFrame,
    detail_frames: dict[str, pd.DataFrame],
) -> None:
    group_cols = ["partition_category_id", "partition_date"]
    for (category_id, partition_date), partition_listings in listings_df.groupby(
        group_cols,
        dropna=False,
    ):
        output_dir = clean_partition_dir(category_id, partition_date)
        output_dir.mkdir(parents=True, exist_ok=True)

        list_ids = set(partition_listings["list_id"].astype(str))
        partition_listings.drop(columns=["raw_json"], errors="ignore").to_csv(
            output_dir / "listings.csv",
            index=False,
            encoding="utf-8-sig",
        )

        partition_attributes = attributes_df[
            attributes_df["list_id"].astype(str).isin(list_ids)
        ]
        if not partition_attributes.empty:
            partition_attributes.to_csv(
                output_dir / "listing_attributes.csv",
                index=False,
                encoding="utf-8-sig",
            )

        for table_name, df in detail_frames.items():
            if df.empty:
                continue
            partition_details = df[df["list_id"].astype(str).isin(list_ids)]
            if not partition_details.empty:
                partition_details.to_csv(
                    output_dir / f"{table_name}.csv",
                    index=False,
                    encoding="utf-8-sig",
                )
