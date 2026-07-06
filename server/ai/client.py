"""LLM clients with OpenAI primary and Gemini fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from server.ai.config import AIConfig


class AIClientError(Exception):
    pass


class AIUnavailableError(AIClientError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIClientError("Model returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise AIClientError("Model JSON must be an object.")

    return payload


def _call_openai(config: AIConfig, prompt: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=config.openai_api_key, timeout=config.request_timeout)
    response = client.chat.completions.create(
        model=config.openai_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You summarize Vietnamese news faithfully. Return JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    return _extract_json(content)


def _call_gemini(config: AIConfig, prompt: str) -> dict[str, Any]:
    from google import genai

    client = genai.Client(api_key=config.gemini_api_key)
    response = client.models.generate_content(
        model=config.gemini_model,
        contents=prompt,
        config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )
    content = getattr(response, "text", "") or ""
    return _extract_json(content)


def generate_json(config: AIConfig, prompt: str) -> tuple[dict[str, Any], str]:
    if not config.is_configured:
        raise AIUnavailableError(
            "AI chưa được cấu hình. Thêm OPENAI_API_KEY hoặc GEMINI_API_KEY trên Render."
        )

    errors: list[str] = []

    if config.has_openai:
        try:
            return _call_openai(config, prompt), "openai"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"openai: {exc}")

    if config.has_gemini:
        try:
            return _call_gemini(config, prompt), "gemini"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"gemini: {exc}")

    if errors:
        raise AIClientError(" ; ".join(errors))

    raise AIUnavailableError(
        "AI chưa được cấu hình. Thêm OPENAI_API_KEY hoặc GEMINI_API_KEY trên Render."
    )
