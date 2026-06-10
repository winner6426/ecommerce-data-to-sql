import logging

from .config import (
    CATEGORY_FILE,
    CLEAN_LAKE_DIR,
    DATA_DIR,
    LOG_DIR,
    LOG_FILE,
    MARKETPLACE_DB_FILE,
)
from .database import write_database
from .lakehouse import (
    load_json,
    load_raw_records,
    write_clean_lakehouse,
)
from .transformers import load_categories_frame, transform_records


def setup_logging() -> None: #Ghi ra log
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )


def run_pipeline(dates: list[str] | None = None, all_dates: bool = False) -> None:
    setup_logging()

    latest_only = not dates and not all_dates
    #Load record từ lakehouse
    raw_records = load_raw_records(dates=dates, latest_only=latest_only) 
    if not raw_records:
        print(f"No raw data found.")
        return  

    categories_df = load_categories_frame(load_json(CATEGORY_FILE, {}))
    listings_df, attributes_df, detail_frames = transform_records(raw_records)
    if listings_df.empty:
        print(f"No listings found in raw data.")
        return

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
    if dates:
        print(f"Processed dates: {', '.join(dates)}")
    elif all_dates:
        print("Processed dates: all")
    else:
        print("Processed dates: latest per category")
    print(f"Saved clean lakehouse: {CLEAN_LAKE_DIR}")
    print(f"Saved SQLite DB: {MARKETPLACE_DB_FILE}")

    logging.info("Listings: %s", len(listings_df))
    logging.info("Attributes: %s", len(attributes_df))
    logging.info("Category groups: %s", counts)
    logging.info("Partitions: %s", partition_count)
