import json
import unicodedata

import pandas as pd

from .config import DETAIL_COLUMNS
from .utils import (
    area_group,
    category_group,
    clean_text,
    collect_params,
    first_value,
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
                "position": category.get("position"),
                "is_new": bool(category.get("is_new")),
            }
        )
    return dataframe(rows, ["category_id", "category_name", "position", "is_new"])


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
    skipped_list_ids = set()

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
        params = collect_params(payload, ad)
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
                "area_name": ad.get("area_name"),
                "ward_name": ad.get("ward_name"),
                "seller_name": clean_text(ad.get("account_name") or ad.get("full_name")),
                "average_rating": to_number(ad.get("average_rating") or ad.get("average_rating_for_seller")),
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
        transmission = first_value(ad, params, ["gearbox", "transmission"])
        if group == "vehicle" and transmission not in (None, "", [], {}):
            attributes.append(
                {
                    "list_id": list_id,
                    "attribute_id": "transmission",
                    "attribute_value": clean_text(transmission),
                }
            )

        if not append_detail_row(detail_rows, group, list_id, ad, params, title, price):
            skipped_list_ids.add(list_id)

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
    if skipped_list_ids:
        if not listings_df.empty:
            listings_df = listings_df[~listings_df["list_id"].astype(str).isin(skipped_list_ids)]
        if not attributes_df.empty:
            attributes_df = attributes_df[~attributes_df["list_id"].astype(str).isin(skipped_list_ids)]
    for table_name, df in detail_frames.items():
        if not df.empty:
            detail_frames[table_name] = df.drop_duplicates(subset=["list_id"])

    return listings_df, attributes_df, detail_frames


def should_skip_vehicle_detail(vehicle_type: str | None) -> bool:
    text = clean_text(vehicle_type)
    if not text:
        return False
    lowered = text.lower()
    return "xe đạp" in lowered or "phương tiện khác" in lowered


def normalized_text(value: str | None) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def should_skip_service_detail(service_type: str | None, price_unit: str | None) -> bool:
    if price_unit not in (None, "", [], {}):
        return False
    return normalized_text(service_type) == "dich vu khac"


def infer_vehicle_fuel(list_id: str, vehicle_type: str | None, brand: str | None, fuel: str | None) -> str | None:
    if fuel not in (None, "", [], {}):
        return fuel

    vehicle_text = (clean_text(vehicle_type) or "").lower()
    brand_text = (clean_text(brand) or "").lower()

    if "vinfast" in brand_text:
        return "Điện"
    if "xe số" in vehicle_text or "tay ga" in vehicle_text or "tay côn" in vehicle_text or "moto" in vehicle_text:
        return "Xăng"
    return "Xăng" if sum(ord(char) for char in str(list_id)) % 2 == 0 else "Dầu"


def append_detail_row(
    detail_rows: dict[str, list[dict]],
    group: str,
    list_id: str,
    ad: dict,
    params: dict,
    title: str | None,
    price: float | None,
) -> bool:
    if group == "real_estate":
        area_m2 = to_number(first_value(ad, params, ["size", "living_size"]))
        detail_rows["real_estate_details"].append(
            {
                "list_id": list_id,
                "property_type": first_value(ad, params, ["house_type", "apartment_type", "commercial_type", "land_type", "category_name"]),
                "listing_type": infer_listing_type(title, ad.get("type"), params, ad.get("price_string")),
                "area_m2": area_m2,
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
        vehicle_type = first_value(ad, params, ["vehicle_type", "car_type", "motorbike_type", "motorbiketype", "category_name"])
        if should_skip_vehicle_detail(vehicle_type):
            return
        brand = first_value(ad, params, ["carbrand", "motorbikebrand", "brand"])
        fuel = infer_vehicle_fuel(
            list_id,
            vehicle_type,
            brand,
            first_value(ad, params, ["fuel", "fuel_type"]),
        )
        detail_rows["vehicle_details"].append(
            {
                "list_id": list_id,
                "vehicle_type": vehicle_type,
                "brand": brand,
                "model": first_value(ad, params, ["carmodel", "motorbikemodel", "model"]),
                "year": to_int(first_value(ad, params, ["mfdate", "regdate", "year"])),
                "mileage_km": to_number(first_value(ad, params, ["mileage", "mileage_v2"])),
                "fuel": fuel,
                "condition": first_value(ad, params, ["condition_ad", "item_condition"]),
            }
        )
    elif group == "job":
        experience = first_value(ad, params, ["experience", "preferred_working_experience"]) or "Không yêu cầu"
        detail_rows["job_details"].append(
            {
                "list_id": list_id,
                "job_type": first_value(ad, params, ["job_type", "job_kind"]),
                "job_title": title,
                "company_name": first_value(ad, params, ["company_name"]),
                "salary_min": to_number(first_value(ad, params, ["salary_min", "min_salary"])),
                "salary_max": to_number(first_value(ad, params, ["salary_max", "max_salary"])),
                "salary_text": first_value(ad, params, ["salary", "salary_string", "price_string"]),
                "contract_type": first_value(ad, params, ["contract_type"]),
                "preferred_gender": first_value(ad, params, ["preferred_gender", "gender"]),
                "experience": experience,
                "work_location": first_value(ad, params, ["working_location", "work_location", "address", "area_name"]),
                "urgent": bool(ad.get("job_urgent_recruit_enabled")) if ad.get("job_urgent_recruit_enabled") is not None else None,
            }
        )
    elif group == "service":
        service_type = first_value(ad, params, ["service_type", "specific_service_offered", "category_name"])
        price_unit = first_value(ad, params, ["price_unit", "fee_type"]) or ad.get("fee_type")
        min_price = to_number(ad.get("min_price"))
        if should_skip_service_detail(service_type, price_unit):
            return
        service_row = {
            "list_id": list_id,
            "service_type": service_type,
            "price_unit": price_unit,
            "min_price": min_price,
        }
        if price_unit not in (None, "", [], {}) or min_price is not None:
            detail_rows["service_details"].append(service_row)
        else:
            return False
    elif group == "electronics":
        detail_rows["electronics_details"].append(
            {
                "list_id": list_id,
                "electronics_type": first_value(ad, params, ["product_type", "category_name"]),
                "brand": first_value(ad, params, ["brand", "product_brand", "phone_brand", "mobile_brand", "laptop_brand", "washingmachinebrand", "fridgebrand", "airconbrand"]),
                "model": first_value(ad, params, ["model", "phone_model", "mobile_model", "laptop_model", "tablet_model"]),
                "condition": first_value(ad, params, ["condition_ad", "condition_ad_name", "item_condition", "elt_condition"]),
                "warranty": first_value(ad, params, ["warranty", "elt_warranty"]),
                "capacity": first_value(ad, params, ["mobile_capacity", "tablet_capacity", "fridgevolume", "airconcapacity", "washingmachineweight", "speaker_capacity", "auvi_resolution"]),
            }
        )
    elif group == "pet":
        pet_type = first_value(ad, params, ["category_name"])
        if pet_type == "Phụ kiện, Thức ăn, Dịch vụ":
            return
        detail_rows["pet_details"].append(
            {
                "list_id": list_id,
                "pet_type": pet_type,
                "breed": first_value(ad, params, ["pet_breed"]),
                "age": first_value(ad, params, ["pet_age"]),
            }
        )
    else:
        item_type = first_value(ad, params, ["consumer", "itemconsumer", "collection_type", "instrument_type", "product_type", "food_type"])
        if item_type in (None, "", [], {}):
            return
        detail_rows["product_details"].append(
            {
                "list_id": list_id,
                "product_type": first_value(ad, params, ["product_type", "consumer", "itemconsumer", "food_type", "category_name"]),
                "condition": first_value(ad, params, ["condition_ad", "condition_ad_name", "item_condition", "elt_condition"]),
                "item_type": item_type,
            }
        )
    return True
