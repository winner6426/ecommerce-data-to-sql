"""Configuration defaults for text2sql."""

from pathlib import Path
import os

from .env_loader import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


DEFAULT_DB_PATH = _resolve_project_path(
    os.environ.get("TEXT2SQL_DB_PATH", PROJECT_ROOT / "data" / "marketplace.db")
)

DEFAULT_MODEL = os.environ.get("TEXT2SQL_MODEL", "gemini-2.5-flash")
DEFAULT_VERTEX_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DEFAULT_VERTEX_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
DEFAULT_MAX_ROUNDS = int(os.environ.get("TEXT2SQL_MAX_ROUNDS", "10"))
DEFAULT_TEMPERATURE = float(os.environ.get("TEXT2SQL_TEMPERATURE", "0.1"))
DEFAULT_MAX_TOKENS = int(os.environ.get("TEXT2SQL_MAX_TOKENS", "4096"))
DEFAULT_SCHEMA_SAMPLE_ROWS = int(os.environ.get("TEXT2SQL_SCHEMA_SAMPLE_ROWS", "3"))
DEFAULT_RESULT_LIMIT = int(os.environ.get("TEXT2SQL_RESULT_LIMIT", "100"))
