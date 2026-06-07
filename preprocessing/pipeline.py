import logging

from .config import (
    AGG_ATTRIBUTES_CSV,
    AGG_LISTINGS_CSV,
    CATEGORY_FILE,
    CLEAN_LAKE_DIR,
    DATA_DIR,
    DETAIL_COLUMNS,
    LOG_DIR,
    LOG_FILE,
    MARKETPLACE_DB_FILE,
    RAW_LAKE_DIR,
)
from .database import write_database
from .lakehouse import (
    load_json,
    load_raw_records,
    migrate_legacy_raw_to_lakehouse,
    write_clean_lakehouse,
)
from .transformers import load_categories_frame, transform_records


def setup_logging() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )


def run_pipeline() -> None:
    setup_logging()
    migrate_legacy_raw_to_lakehouse()

    raw_records = load_raw_records()
    if not raw_records:
        print(f"No raw data found. Expected files under {RAW_LAKE_DIR}.")
        return

    categories_df = load_categories_frame(load_json(CATEGORY_FILE, {}))
    listings_df, attributes_df, detail_frames = transform_records(raw_records)
    if listings_df.empty:
        print("No valid listings found in raw data.")
        return

    AGG_LISTINGS_CSV.parent.mkdir(parents=True, exist_ok=True)
    listings_df.drop(columns=["raw_json"], errors="ignore").to_csv(
        AGG_LISTINGS_CSV,
        index=False,
        encoding="utf-8-sig",
    )
    attributes_df.to_csv(AGG_ATTRIBUTES_CSV, index=False, encoding="utf-8-sig")
    for table_name in DETAIL_COLUMNS:
        df = detail_frames[table_name]
        if not df.empty:
            df.to_csv(DATA_DIR / f"{table_name}.csv", index=False, encoding="utf-8-sig")

    write_clean_lakehouse(listings_df, attributes_df, detail_frames)
    write_database(categories_df, listings_df, attributes_df, detail_frames)

    counts = listings_df["category_group"].value_counts().to_dict()
    partition_count = listings_df[["partition_category_id", "partition_date"]].drop_duplicates().shape[0]

    print("===== PREPROCESS REPORT =====")
    print(f"Raw records: {len(raw_records)}")
    print(f"Listings: {len(listings_df)}")
    print(f"Attributes: {len(attributes_df)}")
    print(f"Category groups: {counts}")
    print(f"Partitions: {partition_count}")
    print(f"Saved clean lakehouse: {CLEAN_LAKE_DIR}")
    print(f"Saved aggregate CSV: {AGG_LISTINGS_CSV}")
    print(f"Saved SQLite DB: {MARKETPLACE_DB_FILE}")

    logging.info("Listings: %s", len(listings_df))
    logging.info("Attributes: %s", len(attributes_df))
    logging.info("Category groups: %s", counts)
    logging.info("Partitions: %s", partition_count)
