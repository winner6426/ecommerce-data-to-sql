"""Command-line runner for the Vertex AI text-to-SQL agent."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from text2sql.agent import run_text2sql
    from text2sql.config import DEFAULT_DB_PATH, DEFAULT_MAX_ROUNDS, DEFAULT_MODEL
else:
    from .agent import run_text2sql
    from .config import DEFAULT_DB_PATH, DEFAULT_MAX_ROUNDS, DEFAULT_MODEL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask a SQLite database a natural-language question.")
    parser.add_argument("question", help="Natural-language question.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Vertex AI model name.")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    parser.add_argument("--conversation", action="store_true", help="Include conversation in JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_text2sql(
        question=args.question,
        db_path=args.db,
        model=args.model,
        max_rounds=args.max_rounds,
        temperature=args.temperature,
        include_conversation=args.conversation,
    )

    if args.json:
        print(json.dumps(result.to_dict(include_conversation=args.conversation), ensure_ascii=False, indent=2))
        return 0

    print("SQL:")
    print(result.sql or "(no sql)")
    print()
    print("Answer:")
    print(result.answer)
    print()
    print(f"Rounds: {result.rounds}; terminated: {result.terminated}; attempts: {len(result.attempts)}")
    return 0 if result.terminated else 2


if __name__ == "__main__":
    raise SystemExit(main())
