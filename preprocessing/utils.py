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


def param_value(param: dict) -> Any:
    for key in ["value", "value_name", "formatted_value", "display_value", "text", "name"]:
        value = param.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def iter_param_items(params: Any):
    if isinstance(params, dict):
        for fallback_key, param in params.items():
            if isinstance(param, dict):
                key = param.get("id") or param.get("key") or param.get("name") or fallback_key
                value = param_value(param)
            else:
                key = fallback_key
                value = param
            if key and value not in (None, "", [], {}):
                yield str(key), value
        return

    if isinstance(params, list):
        for param in params:
            if not isinstance(param, dict):
                continue
            key = param.get("id") or param.get("key") or param.get("name")
            value = param_value(param)
            if key and value not in (None, "", [], {}):
                yield str(key), value


def flatten_params(params: Any) -> dict[str, Any]:
    return {key: value for key, value in iter_param_items(params)}


def collect_params(*sources: dict) -> dict[str, Any]:
    flattened = {}
    param_fields = ["ad_params", "parameters", "params", "parameter", "param", "ad_param"]

    for source in sources:
        if not isinstance(source, dict):
            continue
        for field in param_fields:
            for key, value in iter_param_items(source.get(field)):
                flattened[key] = value

    return flattened


def first_value(ad: dict, params: dict, names: list[str], prefer_params: bool = True) -> Any:
    for name in names:
        if prefer_params and params.get(name) not in (None, ""):
            return params.get(name)
        if ad.get(name) not in (None, ""):
            return ad.get(name)
        if not prefer_params and params.get(name) not in (None, ""):
            return params.get(name)
    return None


def infer_listing_type(
    title: str | None,
    ad_type: Any,
    params: dict,
    price_text: str | None = None,
) -> str | None:
    text = f"{title or ''} {ad_type or ''} {params.get('type') or ''} {price_text or ''}".lower()
    if "cho thue" in text or "cho thuê" in text or "thuê" in text or "rent" in text or "/tháng" in text:
        return "rent"
    if "can mua" in text or "cần mua" in text:
        return "wanted"
    if "can ban" in text or "cần bán" in text or "bán" in text:
        return "sale"
    if ad_type == "s":
        return "sale"
    if ad_type == "u":
        return "rent"
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
