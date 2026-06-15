from __future__ import annotations
from typing import Any
from pathlib import Path
import json

from .config import CAT_FILE, RAW_LAKE_DIR

def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return default
        return json.loads(content)
    return default


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def raw_partition_file(
    category_id: str | int,
    run_date: str,
) -> Path:
    return RAW_LAKE_DIR / f"category_id={category_id}" / f"date={run_date}" / "listings.json"


def load_categories(category_ids: list[int] | None = None) -> list[dict]:
    payload = load_json(CAT_FILE, {})
    categories = payload.get("categories", [])
    if category_ids:
        wanted = set(category_ids)
        categories = [cat for cat in categories if cat.get("cat_id") in wanted]
    return categories
