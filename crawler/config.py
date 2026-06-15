from __future__ import annotations

from typing import Any
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
RAW_LAKE_DIR = DATA_DIR / "raw"
CAT_FILE = DATA_DIR / "cat_id.json"

DATA_DIR.mkdir(exist_ok=True)

DEFAULT_PAGE_START = 0
DEFAULT_PAGE_END = 1
DEFAULT_LIMIT = 20
DEFAULT_SLEEP_LIST = 1.5
DEFAULT_SLEEP_DETAIL = 0.8
DEFAULT_TIMEOUT_SECONDS = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Apple Silicon)",
    "Accept": "application/json",
}