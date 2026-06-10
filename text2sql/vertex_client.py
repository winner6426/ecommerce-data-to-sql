"""Small Vertex AI wrapper used by the text-to-SQL agent."""

from __future__ import annotations

from typing import Any
import os

from .env_loader import load_dotenv


load_dotenv()


def _split_system_prompt(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, str]]]:
    system_parts: list[str] = []
    rest: list[dict[str, str]] = []
    for message in messages:
        if message.get("role") == "system":
            system_parts.append(message.get("content", ""))
        else:
            rest.append(message)
    system_prompt = "\n\n".join(part for part in system_parts if part).strip() or None
    return system_prompt, rest


def _flatten_messages(messages: list[dict[str, str]]) -> str:
    chunks: list[str] = []
    for message in messages:
        role = message.get("role", "user").upper()
        chunks.append(f"{role}:\n{message.get('content', '')}")
    return "\n\n".join(chunks)


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    parts: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    return "\n".join(parts)


class VertexAIClient:
    """Google Gen AI client configured for Vertex AI."""

    def __init__(
        self,
        project: str | None = None,
        location: str | None = None,
    ):
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency google-genai. Run: pip install -r requirements.txt"
            ) from exc

        project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = location or os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
        if not project:
            raise RuntimeError("Set GOOGLE_CLOUD_PROJECT before using Vertex AI.")

        self._types = types
        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=types.HttpOptions(api_version="v1"),
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        system_prompt, conversation = _split_system_prompt(messages)
        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        response = self._client.models.generate_content(
            model=model,
            contents=_flatten_messages(conversation),
            config=config,
        )
        return _extract_text(response)
