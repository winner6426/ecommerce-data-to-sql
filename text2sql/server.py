"""FastAPI API for the Vertex AI text-to-SQL agent."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import normalize_question_text, run_text2sql
from .config import DEFAULT_DB_PATH, DEFAULT_MAX_ROUNDS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from .schema import SchemaInspector
from .sqlite_tool import execute_sqlite_sql


app = FastAPI(title="Vertex AI SQLite Text2SQL Agent", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    db_path: Optional[str] = None
    model: Optional[str] = None
    vertex_project: Optional[str] = None
    vertex_location: Optional[str] = None
    max_rounds: Optional[int] = None
    temperature: Optional[float] = None
    external_context: Optional[str] = None
    include_conversation: bool = False


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    db_path: Optional[str] = None
    row_limit: int = Field(100, ge=1, le=500)


def _local_answer(question: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    normalized = normalize_question_text(question).replace("?", " ")
    sql = ""

    is_count_question = "bao nhieu" in normalized or "so luong" in normalized or "co bao" in normalized
    is_real_estate = "bat dong san" in normalized or all(term in normalized for term in ("dong", "san"))
    is_hanoi = "ha noi" in normalized or all(term in normalized for term in ("ha", "noi"))
    is_root_category = "danh muc goc" in normalized or all(term in normalized for term in ("danh", "muc", "goc"))
    is_vehicle_area_top = "top" in normalized and ("khu vuc" in normalized or all(term in normalized for term in ("khu", "vuc"))) and "xe" in normalized
    is_avg_price = "gia trung binh" in normalized or all(term in normalized for term in ("gia", "trung", "binh"))

    if is_count_question and is_real_estate and is_hanoi:
        sql = """
SELECT COUNT(*) AS total
FROM listings
WHERE category_group = 'real_estate'
  AND region_name = 'Hà Nội'
"""
        label = "tin bất động sản ở Hà Nội"
    elif is_root_category and is_count_question:
        sql = """
SELECT COALESCE(c.category_name, l.category_group) AS danh_muc_goc,
       COUNT(*) AS so_tin
FROM listings l
LEFT JOIN categories c ON c.category_id = l.root_category_id
GROUP BY COALESCE(c.category_name, l.category_group)
ORDER BY so_tin DESC
"""
        label = "tin theo từng danh mục gốc"
    elif is_vehicle_area_top:
        sql = """
SELECT area_name AS khu_vuc,
       COUNT(*) AS so_tin
FROM listings
WHERE category_group = 'vehicle'
GROUP BY area_name
ORDER BY so_tin DESC
LIMIT 10
"""
        label = "khu vực có nhiều tin xe nhất"
    elif is_avg_price and ("nhom danh muc" in normalized or "category_group" in normalized or all(term in normalized for term in ("nhom", "danh", "muc"))):
        sql = """
SELECT category_group AS nhom_danh_muc,
       ROUND(AVG(price), 0) AS gia_trung_binh
FROM listings
WHERE price IS NOT NULL
GROUP BY category_group
ORDER BY gia_trung_binh DESC
"""
        label = "giá trung bình theo nhóm danh mục"
    else:
        return None

    result = execute_sqlite_sql(sql, db_path, row_limit=100)
    if not result.get("ok"):
        return None

    rows = result.get("rows", [])
    if len(rows) == 1 and len(rows[0]) == 1:
        value = next(iter(rows[0].values()))
        answer = f"Có {value} {label}."
    elif rows:
        lines = [f"Kết quả {label}:"]
        for index, row in enumerate(rows[:10], start=1):
            values = ", ".join(f"{key}: {value}" for key, value in row.items())
            lines.append(f"{index}. {values}")
        answer = "\n".join(lines)
    else:
        answer = f"Không tìm thấy dữ liệu cho câu hỏi về {label}."

    return {
        "question": question,
        "db_path": str(Path(db_path).resolve()),
        "model": "local-sql-fallback",
        "answer": answer,
        "sql": result.get("sql", sql),
        "terminated": True,
        "rounds": 0,
        "attempts": [
            {
                "sql": result.get("sql", sql),
                "ok": True,
                "error": None,
                "preview_csv": result.get("csv", ""),
                "preview_row_count": result.get("preview_row_count", 0),
                "truncated": result.get("truncated", False),
            }
        ],
    }


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="UI files were not found.")
    return FileResponse(index_path)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "default_model": DEFAULT_MODEL,
        "default_db_path": str(DEFAULT_DB_PATH),
    }


@app.get("/schema")
def schema(db_path: Optional[str] = None) -> dict[str, str]:
    try:
        path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
        return {"db_path": str(path), "schema": SchemaInspector(path).to_markdown()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/query")
def query(body: QueryRequest) -> dict:
    try:
        path = Path(body.db_path).resolve() if body.db_path else DEFAULT_DB_PATH
        return execute_sqlite_sql(body.sql, path, row_limit=body.row_limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ask")
def ask(body: AskRequest) -> dict:
    try:
        result = run_text2sql(
            question=body.question,
            db_path=body.db_path or DEFAULT_DB_PATH,
            model=body.model or DEFAULT_MODEL,
            vertex_project=body.vertex_project,
            vertex_location=body.vertex_location,
            max_rounds=body.max_rounds or DEFAULT_MAX_ROUNDS,
            temperature=DEFAULT_TEMPERATURE if body.temperature is None else body.temperature,
            external_context=body.external_context,
            include_conversation=body.include_conversation,
        )
        return result.to_dict(include_conversation=body.include_conversation)
    except Exception as exc:
        fallback = _local_answer(body.question, body.db_path or DEFAULT_DB_PATH)
        if fallback is not None:
            fallback["answer"] += "\n\nGhi chú: Vertex AI chưa chạy được, nên hệ thống dùng truy vấn SQLite local cho mẫu câu hỏi này."
            return fallback
        raise HTTPException(status_code=400, detail=str(exc)) from exc
