import json

import pandas as pd

from .config import DETAIL_COLUMNS
from .utils import (
    area_group,
    category_group,
    clean_text,
    first_value,
    flatten_params,
    infer_listing_type,
    normalize_sqlite_values,
    price_group,
    root_category_id,
    to_int,
    to_number,
)


def load_categories_frame(category_payload: dict) -> pd.DataFrame:
    rows = []
    for category in category_payload.get("categories", []):
        rows.append(
            {
                "category_id": category.get("cat_id"),
                "category_name": category.get("cat_name"),
                "link": category.get("link"),
                "position": category.get("position"),
                "is_new": bool(category.get("is_new")),
            }
        )
    return dataframe(rows, ["category_id", "category_name", "link", "position", "is_new"])


def dataframe(rows: list[dict], columns: list[str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if columns:
        for column in columns:
            if column not in df.columns:
                df[column] = None
        df = df[columns]
    return normalize_sqlite_values(df)


def transform_records(raw_records: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    listings = []
    attributes = []
    detail_rows = {table_name: [] for table_name in DETAIL_COLUMNS}

    for raw_record in raw_records:
        raw_key = raw_record["raw_key"]
        payload = raw_record["payload"]
        ad = payload.get("ad", {}) if isinstance(payload, dict) else {}
        if not ad:
            continue

        list_id = str(ad.get("list_id") or raw_key)
        category_id = to_int(ad.get("category"))
        root_id = root_category_id(category_id)
        partition_category_id = raw_record.get("partition_category_id") or root_id
        partition_date = raw_record.get("partition_date")
        params = flatten_params(ad.get("params"))
        group = category_group(category_id)
        price = to_number(ad.get("price"))
        title = clean_text(ad.get("subject"))

        listings.append(
            {
                "list_id": list_id,
                "ad_id": str(ad.get("ad_id")) if ad.get("ad_id") is not None else None,
                "category_id": category_id,
                "root_category_id": root_id,
                "partition_category_id": partition_category_id,
                "partition_date": partition_date,
                "category_group": group,
                "category_name": ad.get("category_name"),
                "title": title,
                "description": clean_text(ad.get("body")),
                "price": price,
                "price_text": ad.get("price_string"),
                "date_text": ad.get("date"),
                "list_time": to_int(ad.get("list_time")),
                "region_id": to_int(ad.get("region_v2") or ad.get("region")),
                "region_name": ad.get("region_name"),
                "area_id": to_int(ad.get("area_v2") or ad.get("area")),
                "area_name": ad.get("area_name"),
                "ward_id": to_int(ad.get("ward")),
                "ward_name": ad.get("ward_name"),
                "latitude": to_number(ad.get("latitude")),
                "longitude": to_number(ad.get("longitude")),
                "seller_account_id": str(ad.get("account_id")) if ad.get("account_id") is not None else None,
                "seller_name": clean_text(ad.get("account_name") or ad.get("full_name")),
                "company_ad": bool(ad.get("company_ad")) if ad.get("company_ad") is not None else None,
                "status": ad.get("status"),
                "image_count": to_int(ad.get("number_of_images")),
                "raw_json": json.dumps(payload, ensure_ascii=False),
            }
        )

        for attr_id, attr_value in params.items():
            attributes.append(
                {
                    "list_id": list_id,
                    "attribute_id": attr_id,
                    "attribute_value": clean_text(attr_value),
                }
            )

        append_detail_row(detail_rows, group, list_id, ad, params, title, price)

    listings_df = dataframe(listings)
    attributes_df = dataframe(attributes, ["list_id", "attribute_id", "attribute_value"])
    detail_frames = {
        table_name: dataframe(rows, DETAIL_COLUMNS[table_name])
        for table_name, rows in detail_rows.items()
    }

    if not listings_df.empty:
        listings_df = listings_df.drop_duplicates(subset=["list_id"])
    if not attributes_df.empty:
        attributes_df = attributes_df.drop_duplicates(subset=["list_id", "attribute_id"])
    for table_name, df in detail_frames.items():
        if not df.empty:
            detail_frames[table_name] = df.drop_duplicates(subset=["list_id"])

    return listings_df, attributes_df, detail_frames


def append_detail_row(
    detail_rows: dict[str, list[dict]],
    group: str,
    list_id: str,
    ad: dict,
    params: dict,
    title: str | None,
    price: float | None,
) -> None:
    if group == "real_estate":
        area_m2 = to_number(first_value(ad, params, ["size", "living_size"]))
        detail_rows["real_estate_details"].append(
            {
                "list_id": list_id,
                "property_type": first_value(ad, params, ["house_type", "apartment_type", "commercial_type", "land_type", "category_name"]),
                "listing_type": infer_listing_type(title, ad.get("type"), params),
                "area_m2": area_m2,
                "living_area_m2": to_number(ad.get("living_size")),
                "width_m": to_number(first_value(ad, params, ["width"])),
                "length_m": to_number(first_value(ad, params, ["length"])),
                "rooms": to_number(first_value(ad, params, ["rooms"])),
                "toilets": to_number(first_value(ad, params, ["toilets"])),
                "floors": to_number(first_value(ad, params, ["floors"])),
                "legal_document": first_value(ad, params, ["property_legal_document"]),
                "furnishing": first_value(ad, params, ["furnishing_sell", "furnishing_rent"]),
                "street_name": ad.get("street_name"),
                "price_per_m2": price / area_m2 if price and area_m2 else None,
                "area_group": area_group(area_m2),
                "price_group": price_group(price),
            }
        )
    elif group == "vehicle":
        detail_rows["vehicle_details"].append(
            {
                "list_id": list_id,
                "vehicle_type": first_value(ad, params, ["vehicle_type", "car_type", "motorbike_type"]),
                "brand": first_value(ad, params, ["carbrand", "motorbikebrand", "brand"]),
                "model": first_value(ad, params, ["carmodel", "motorbikemodel", "model"]),
                "year": to_int(first_value(ad, params, ["mfdate", "regdate", "year"])),
                "mileage_km": to_number(first_value(ad, params, ["mileage", "mileage_v2"])),
                "fuel": first_value(ad, params, ["fuel", "fuel_type"]),
                "transmission": first_value(ad, params, ["gearbox", "transmission"]),
                "condition": first_value(ad, params, ["condition_ad", "item_condition"]),
                "color": first_value(ad, params, ["color"]),
                "origin": first_value(ad, params, ["origin"]),
            }
        )
    elif group == "job":
        detail_rows["job_details"].append(
            {
                "list_id": list_id,
                "job_type": first_value(ad, params, ["job_type", "job_kind"]),
                "position": first_value(ad, params, ["job_position", "position"]),
                "company_name": first_value(ad, params, ["company_name"]),
                "salary_min": to_number(first_value(ad, params, ["salary_min", "min_salary"])),
                "salary_max": to_number(first_value(ad, params, ["salary_max", "max_salary"])),
                "salary_text": first_value(ad, params, ["salary", "salary_string"]),
                "experience": first_value(ad, params, ["experience"]),
                "education": first_value(ad, params, ["education"]),
                "gender": first_value(ad, params, ["gender"]),
                "work_location": first_value(ad, params, ["working_location", "work_location"]),
            }
        )
    elif group == "service":
        detail_rows["service_details"].append(
            {
                "list_id": list_id,
                "service_type": first_value(ad, params, ["service_type", "specific_service_offered"]),
                "provider_type": first_value(ad, params, ["provider_type"]),
                "price_unit": first_value(ad, params, ["price_unit", "fee_type"]) or ad.get("fee_type"),
            }
        )
    else:
        detail_rows["product_details"].append(
            {
                "list_id": list_id,
                "product_type": first_value(ad, params, ["product_type", "category_name"]),
                "brand": first_value(ad, params, ["brand", "phone_brand", "mobile_brand", "laptop_brand"]),
                "model": first_value(ad, params, ["model", "phone_model", "mobile_model", "laptop_model"]),
                "condition": first_value(ad, params, ["condition_ad", "item_condition"]),
                "warranty": first_value(ad, params, ["warranty"]),
                "color": first_value(ad, params, ["color"]),
                "origin": first_value(ad, params, ["origin"]),
            }
        )
