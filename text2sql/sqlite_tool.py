"""Safe read-only SQLite execution for the agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import io
import re
import sqlite3
import time


FORBIDDEN_SQL_RE = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"vacuum|pragma|reindex|analyze|begin|commit|rollback|grant|revoke"
    r")\b",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.DOTALL)


def validate_read_only_sql(sql: str) -> str:
    normalized = COMMENT_RE.sub(" ", sql or "").strip()
    if not normalized:
        raise ValueError("SQL is empty.")
    if normalized.count(";") > 1 or (";" in normalized and not normalized.endswith(";")):
        raise ValueError("Only one SQL statement is allowed.")
    if normalized.endswith(";"):
        normalized = normalized[:-1].strip()
    if not re.match(r"^(select|with)\b", normalized, re.IGNORECASE):
        raise ValueError("Only SELECT/WITH queries are allowed.")
    forbidden = FORBIDDEN_SQL_RE.search(normalized)
    if forbidden:
        raise ValueError(f"Forbidden SQL keyword: {forbidden.group(1).upper()}.")
    return normalized


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    return str(value)


def _rows_to_csv(columns: list[str], rows: list[dict[str, Any]], max_chars: int) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in columns})
    csv_text = output.getvalue().strip()
    if len(csv_text) > max_chars:
        csv_text = csv_text[:max_chars]
        last_newline = csv_text.rfind("\n")
        if last_newline > 0:
            csv_text = csv_text[:last_newline]
    return csv_text


def _quoted_object_patterns(name: str) -> str:
    variants = [
        name,
        '"' + name.replace('"', '""') + '"',
        "`" + name.replace("`", "``") + "`",
        "[" + name.replace("]", "]]") + "]",
    ]
    return "|".join(re.escape(variant) for variant in variants)


def _references_object(sql: str, object_name: str) -> bool:
    object_pattern = _quoted_object_patterns(object_name)
    schema_pattern = r'(?:(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|\w+)\s*\.\s*)?'
    pattern = re.compile(
        rf"\b(?:from|join)\s+{schema_pattern}(?:{object_pattern})(?=\s|,|\)|$)",
        re.IGNORECASE,
    )
    return bool(pattern.search(sql))


def _referenced_view_name(conn: sqlite3.Connection, sql: str) -> str | None:
    views = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'view'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    for row in views:
        view_name = row[0]
        if _references_object(sql, view_name):
            return view_name
    return None


def execute_sqlite_sql(
    sql: str,
    db_path: str | Path,
    row_limit: int = 100,
    max_csv_chars: int = 8000,
    allow_views: bool = False,
) -> dict[str, Any]:
    started_at = time.time()
    try:
        safe_sql = validate_read_only_sql(sql)
    except ValueError as exc:
        return {
            "ok": False,
            "sql": sql,
            "error": str(exc),
            "content": f"SQL validation error: {exc}",
            "elapsed_seconds": 0.0,
        }

    db_path = Path(db_path).resolve()
    if not db_path.exists():
        return {
            "ok": False,
            "sql": safe_sql,
            "error": f"SQLite database not found: {db_path}",
            "content": f"SQLite database not found: {db_path}",
            "elapsed_seconds": 0.0,
        }

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        if not allow_views:
            view_name = _referenced_view_name(conn, safe_sql)
            if view_name:
                return {
                    "ok": False,
                    "sql": safe_sql,
                    "error": f"SQLite views are disabled for text2sql: {view_name}",
                    "content": (
                        "SQL error: SQLite views are disabled for text2sql. "
                        f"Use the base tables and explicit joins instead of view {view_name}."
                    ),
                    "elapsed_seconds": round(time.time() - started_at, 4),
                }
        cursor = conn.execute(safe_sql)
        columns = [desc[0] for desc in cursor.description or []]
        fetched = cursor.fetchmany(row_limit + 1)
        truncated = len(fetched) > row_limit
        rows = [{key: _json_safe(row[key]) for key in row.keys()} for row in fetched[:row_limit]]
        csv_text = _rows_to_csv(columns, rows, max_csv_chars) if columns else ""
        content = (
            "Query executed successfully.\n"
            f"Rows returned in preview: {len(rows)}"
            + (" (truncated)" if truncated else "")
        )
        if csv_text:
            content += f"\n\n```csv\n{csv_text}\n```"
        elif columns:
            content += "\n\nThe query returned no rows."
        else:
            content += "\n\nThe query returned no result set."
        return {
            "ok": True,
            "sql": safe_sql,
            "columns": columns,
            "rows": rows,
            "csv": csv_text,
            "preview_row_count": len(rows),
            "truncated": truncated,
            "content": content,
            "elapsed_seconds": round(time.time() - started_at, 4),
        }
    except sqlite3.Error as exc:
        return {
            "ok": False,
            "sql": safe_sql,
            "error": str(exc),
            "content": f"SQL error: {exc}",
            "elapsed_seconds": round(time.time() - started_at, 4),
        }
    finally:
        if conn is not None:
            conn.close()
