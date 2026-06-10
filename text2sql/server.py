"""FastAPI API for the Vertex AI text-to-SQL agent."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agent import run_text2sql
from .config import DEFAULT_DB_PATH, DEFAULT_MAX_ROUNDS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from .schema import SchemaInspector


app = FastAPI(title="Vertex AI SQLite Text2SQL Agent", version="0.1.0")


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
