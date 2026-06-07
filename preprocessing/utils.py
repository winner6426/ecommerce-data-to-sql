import json
import re
from typing import Any

import pandas as pd

from .config import (
    JOB_CATEGORIES,
    REAL_ESTATE_CATEGORIES,
    SERVICE_CATEGORIES,
    VEHICLE_CATEGORIES,
)


def to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).lower().replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def to_int(value: Any) -> int | None:
    number = to_number(value)
    return int(number) if number is not None else None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False)
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def sqlite_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, tuple):
        return json.dumps(list(value), ensure_ascii=False)
    return value


def normalize_sqlite_values(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.map(sqlite_value)


def root_category_id(category_id: int | None) -> int | None:
    if category_id is None:
        return None
    if category_id < 1000:
        return category_id
    return (category_id // 1000) * 1000


def category_group(category_id: int | None) -> str:
    root_id = root_category_id(category_id)
    if root_id in REAL_ESTATE_CATEGORIES:
        return "real_estate"
    if root_id in VEHICLE_CATEGORIES:
        return "vehicle"
    if root_id in JOB_CATEGORIES:
        return "job"
    if root_id in SERVICE_CATEGORIES:
        return "service"
    return "product"


def flatten_params(params: Any) -> dict[str, Any]:
    flattened = {}
    if not isinstance(params, list):
        return flattened

    for param in params:
        if not isinstance(param, dict):
            continue
        key = param.get("id") or param.get("key") or param.get("name")
        value = param.get("value")
        if key and value not in (None, ""):
            flattened[str(key)] = value
    return flattened


def first_value(ad: dict, params: dict, names: list[str]) -> Any:
    for name in names:
        if ad.get(name) not in (None, ""):
            return ad.get(name)
        if params.get(name) not in (None, ""):
            return params.get(name)
    return None


def infer_listing_type(title: str | None, ad_type: Any, params: dict) -> str | None:
    text = f"{title or ''} {ad_type or ''} {params.get('type') or ''}".lower()
    if "cho thue" in text or "cho thuê" in text or "thuê" in text or "rent" in text:
        return "rent"
    if "can mua" in text or "cần mua" in text:
        return "wanted"
    if "can ban" in text or "cần bán" in text or "bán" in text:
        return "sale"
    return None


def price_group(price: float | None) -> str | None:
    if price is None or price <= 0:
        return None
    billion = price / 1_000_000_000
    if billion < 1:
        return "under_1b"
    if billion < 3:
        return "1_3b"
    if billion < 5:
        return "3_5b"
    if billion < 10:
        return "5_10b"
    return "over_10b"


def area_group(area_m2: float | None) -> str | None:
    if area_m2 is None or area_m2 <= 0:
        return None
    if area_m2 < 30:
        return "very_small"
    if area_m2 < 60:
        return "small"
    if area_m2 < 100:
        return "medium"
    if area_m2 < 300:
        return "large"
    return "very_large"
