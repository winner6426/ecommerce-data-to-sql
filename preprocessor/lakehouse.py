import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .config import CLEAN_LAKE_DIR, RAW_LAKE_DIR
from .utils import clean_text, to_int


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def clean_partition_dir(category_id: Any, partition_date: Any) -> Path:
    category_value = int(category_id) if pd.notna(category_id) else "unknown"
    date_value = clean_text(partition_date) or date.today().isoformat()
    return CLEAN_LAKE_DIR / f"category_id={category_value}" / f"date={date_value}"


def parse_partition_value(path: Path, prefix: str) -> str | None:
    for part in path.parts:
        if part.startswith(prefix):
            return part.split("=", 1)[1]
    return None


def raw_partition_paths() -> list[Path]:
    return sorted(RAW_LAKE_DIR.glob("category_id=*/date=*/listings.json"))


def select_raw_partition_paths(
    dates: list[str] | None = None,
    latest_only: bool = True,
) -> list[Path]:
    paths = raw_partition_paths()
    if dates:
        selected_dates = set(dates)
        return [
            path
            for path in paths
            if parse_partition_value(path, "date=") in selected_dates
        ]
    if not latest_only:
        return paths

    latest_by_category: dict[str, tuple[str, Path]] = {}
    for path in paths:
        category_id = parse_partition_value(path, "category_id=") or "unknown"
        partition_date = parse_partition_value(path, "date=") or ""
        current = latest_by_category.get(category_id)
        if current is None or partition_date > current[0]:
            latest_by_category[category_id] = (partition_date, path)
    return sorted(path for _, path in latest_by_category.values())


def load_raw_records(
    dates: list[str] | None = None,
    latest_only: bool = True,
) -> list[dict]:
    records_by_list_id = {}

    for path in select_raw_partition_paths(dates=dates, latest_only=latest_only):
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

        #Xóa các file cũ trong thư mục 
        for stale_file in output_dir.glob("*.csv"):
            stale_file.unlink()

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
