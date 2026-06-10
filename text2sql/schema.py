"""SQLite schema introspection for prompt construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sqlite3


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def compact_value(value: Any, max_length: int = 120) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    text = str(value).replace("\r", " ").replace("\n", " ").replace("|", "/").strip()
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    default: str
    primary_key: bool


@dataclass(frozen=True)
class TableInfo:
    name: str
    kind: str
    row_count: int | None
    columns: list[ColumnInfo]
    sample_rows: list[dict[str, str]]
    foreign_keys: list[dict[str, str]]


class SchemaInspector:
    """Read table metadata, row counts, sample rows and foreign keys."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def inspect(self, sample_rows: int = 3) -> list[TableInfo]:
        with self._connect() as conn:
            objects = conn.execute(
                """
                SELECT name, type
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()

            tables: list[TableInfo] = []
            for obj in objects:
                name = obj["name"]
                quoted = quote_identifier(name)
                columns = [
                    ColumnInfo(
                        name=row["name"],
                        type=row["type"] or "",
                        nullable=not bool(row["notnull"]),
                        default="" if row["dflt_value"] is None else str(row["dflt_value"]),
                        primary_key=bool(row["pk"]),
                    )
                    for row in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
                ]

                row_count: int | None = None
                if obj["type"] == "table":
                    try:
                        row_count = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
                    except sqlite3.Error:
                        row_count = None

                foreign_keys: list[dict[str, str]] = []
                try:
                    for fk in conn.execute(f"PRAGMA foreign_key_list({quoted})").fetchall():
                        foreign_keys.append(
                            {
                                "from": compact_value(fk["from"]),
                                "to_table": compact_value(fk["table"]),
                                "to": compact_value(fk["to"]),
                            }
                        )
                except sqlite3.Error:
                    pass

                samples: list[dict[str, str]] = []
                if sample_rows > 0:
                    try:
                        cursor = conn.execute(f"SELECT * FROM {quoted} LIMIT ?", (sample_rows,))
                        for row in cursor.fetchall():
                            samples.append({key: compact_value(row[key]) for key in row.keys()})
                    except sqlite3.Error:
                        samples = []

                tables.append(
                    TableInfo(
                        name=name,
                        kind=obj["type"],
                        row_count=row_count,
                        columns=columns,
                        sample_rows=samples,
                        foreign_keys=foreign_keys,
                    )
                )
            return tables

    def to_markdown(self, sample_rows: int = 3, max_chars: int = 45000) -> str:
        tables = self.inspect(sample_rows=sample_rows)
        lines = [
            "# SQLite schema",
            f"Database file: {self.db_path}",
            f"Objects: {', '.join(table.name for table in tables)}",
            "",
            "Join hints:",
            "- listings.list_id is the central listing key.",
            "- listings contains shared listing fields: category, title, price, date, region_name, area_name, ward_name, seller and status.",
            "- Detail tables usually join back to listings on list_id.",
            "- Detail tables contain type-specific fields only; do not assume they contain region_name, area_name, category_name or category_group.",
            "- When filtering by location/category/listing metadata while using a detail table, join the detail table to listings on list_id.",
            "- listing_attributes stores additional key/value attributes by list_id.",
            "",
        ]

        for table in tables:
            count_text = "unknown" if table.row_count is None else str(table.row_count)
            lines.append(f"## {table.name} ({table.kind}, rows: {count_text})")
            lines.append("| column | type | nullable | default | pk |")
            lines.append("|---|---|---:|---|---:|")
            for col in table.columns:
                lines.append(
                    f"| {col.name} | {col.type} | {'yes' if col.nullable else 'no'} | "
                    f"{compact_value(col.default)} | {'yes' if col.primary_key else 'no'} |"
                )

            if table.foreign_keys:
                lines.append("")
                lines.append("Foreign keys:")
                for fk in table.foreign_keys:
                    lines.append(f"- {fk['from']} -> {fk['to_table']}.{fk['to']}")

            if table.sample_rows:
                columns = list(table.sample_rows[0].keys())
                lines.append("")
                lines.append("Sample rows:")
                lines.append("| " + " | ".join(columns) + " |")
                lines.append("|" + "|".join("---" for _ in columns) + "|")
                for row in table.sample_rows:
                    lines.append("| " + " | ".join(row.get(col, "") for col in columns) + " |")
            lines.append("")

        markdown = "\n".join(lines)
        if len(markdown) > max_chars:
            return markdown[:max_chars] + "\n\n[Schema truncated.]"
        return markdown
