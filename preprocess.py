import json
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine


DATA_DIR = Path("data")
LOG_DIR = Path("logs")

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

RAW_FILE = DATA_DIR / "all_raw_data.json"

CSV_FILE = DATA_DIR / "cleaned_data.csv"

SALE_FILE = DATA_DIR / "sale_data.csv"

RENT_FILE = DATA_DIR / "rent_data.csv"

DB_FILE = DATA_DIR / "real_estate.db"

LOG_FILE = LOG_DIR / "crawler.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)


def main():

    # kiểm tra file raw json

    if not RAW_FILE.exists():
        print("Không tìm thấy all_raw_data.json")
        return

    # load dữ liệu raw

    with open(RAW_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []

    # lấy các field cần thiết

    for key, value in data.items():

        ad = value.get("ad", {})

        record = {
            "ad_id": ad.get("ad_id"),
            "list_id": ad.get("list_id"),
            "title": ad.get("subject"),
            "price": ad.get("price"),
            "area": ad.get("size"),
            "district": ad.get("area_name"),
            "ward": ad.get("ward_name"),
            "city": ad.get("region_name"),
            "property_type": ad.get("category_name"),
            "rooms": ad.get("rooms"),
            "toilets": ad.get("toilets"),
            "floors": ad.get("floors"),
            "date": ad.get("date"),
            "body": ad.get("body"),
        }

        records.append(record)

    # tạo dataframe

    df = pd.DataFrame(records)

    print("\n===== RAW DATAFRAME =====")

    print(df.head())

    print("\nShape:", df.shape)

    logging.info(f"Raw dataframe shape: {df.shape}")

    # xóa duplicate

    df.drop_duplicates(
        subset=["ad_id"],
        inplace=True
    )

    # convert kiểu dữ liệu số

    for col in [
        "price",
        "area",
        "rooms",
        "toilets",
        "floors",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    before_clean = len(df)

    # xóa dữ liệu thiếu

    df.dropna(
        subset=["price", "area"],
        inplace=True
    )

    # lọc dữ liệu không hợp lệ

    df = df[df["price"] > 0]

    df = df[df["area"] > 0]

    df = df[df["price"] < 1_000_000_000_000]

    df = df[df["area"] < 10_000]

    # bỏ cột ít dùng

    df.drop(
        columns=["toilets", "floors"],
        inplace=True
    )

    # fill missing rooms

    if df["rooms"].notna().sum() > 0:

        df["rooms"] = df["rooms"].fillna(
            df["rooms"].median()
        )

    else:

        df["rooms"] = df["rooms"].fillna(0)

    # tạo feature mới

    df["price_per_m2"] = (
        df["price"] / df["area"]
    )

    df["price_billion"] = (
        df["price"] / 1_000_000_000
    )

    # phân loại bán / thuê

    df["listing_type"] = (
        df["title"]
        .astype(str)
        .str.lower()
        .apply(
            lambda x:
            "rent"
            if (
                "thuê" in x
                or "cho thuê" in x
            )
            else "sale"
        )
    )

    # nhóm diện tích

    df["area_group"] = pd.cut(
        df["area"],
        bins=[0, 30, 60, 100, 300, 10000],
        labels=[
            "very_small",
            "small",
            "medium",
            "large",
            "very_large"
        ]
    )

    # nhóm giá

    df["price_group"] = pd.cut(
        df["price_billion"],
        bins=[0, 1, 3, 5, 10, 1000],
        labels=[
            "under_1b",
            "1_3b",
            "3_5b",
            "5_10b",
            "over_10b"
        ]
    )

    after_clean = len(df)

    # report

    print("\n===== CLEANING REPORT =====")

    print("Before:", before_clean)

    print("After:", after_clean)

    print("Removed:", before_clean - after_clean)

    print("\n===== LISTING TYPE =====")

    print(
        df["listing_type"]
        .value_counts()
    )

    print("\n===== FINAL MISSING VALUES =====")

    print(df.isnull().sum())

    print("\n===== NUMERICAL SUMMARY =====")

    print(
        df[
            [
                "price",
                "area",
                "rooms",
                "price_per_m2",
                "price_billion"
            ]
        ].describe()
    )

    # tách dữ liệu bán và thuê

    sale_df = df[
        df["listing_type"] == "sale"
    ]

    rent_df = df[
        df["listing_type"] == "rent"
    ]

    # lưu csv

    df.to_csv(
        CSV_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    sale_df.to_csv(
        SALE_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    rent_df.to_csv(
        RENT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # lưu sqlite

    engine = create_engine(
        f"sqlite:///{DB_FILE}"
    )

    df.to_sql(
        "properties",
        engine,
        if_exists="replace",
        index=False
    )

    sale_df.to_sql(
        "sale_properties",
        engine,
        if_exists="replace",
        index=False
    )

    rent_df.to_sql(
        "rent_properties",
        engine,
        if_exists="replace",
        index=False
    )

    # report cuối

    print(f"\nSaved CSV: {CSV_FILE}")

    print(f"Saved SALE CSV: {SALE_FILE}")

    print(f"Saved RENT CSV: {RENT_FILE}")

    print(f"Saved SQLite DB: {DB_FILE}")

    print(f"\nTotal rows: {len(df)}")

    print(f"Sale rows: {len(sale_df)}")

    print(f"Rent rows: {len(rent_df)}")

    logging.info(f"Cleaned rows: {len(df)}")

    logging.info(f"Sale rows: {len(sale_df)}")

    logging.info(f"Rent rows: {len(rent_df)}")


if __name__ == "__main__":
    main()