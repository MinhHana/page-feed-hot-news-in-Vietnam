"""Grok (xAI) LLM client for news brief generation."""

from __future__ import annotations

import json
import re
from typing import Any

from server.ai.config import AIConfig, XAI_API_BASE_URL


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


def _call_grok(config: AIConfig, prompt: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(
        api_key=config.xai_api_key,
        base_url=XAI_API_BASE_URL,
        timeout=config.request_timeout,
    )
    response = client.chat.completions.create(
        model=config.grok_model,
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


def generate_json(config: AIConfig, prompt: str) -> tuple[dict[str, Any], str]:
    if not config.is_configured:
        raise AIUnavailableError(
            "AI chưa được cấu hình. Thêm XAI_API_KEY (Grok API key) trên Render."
        )

    try:
        return _call_grok(config, prompt), "grok"
    except Exception as exc:  # noqa: BLE001
        raise AIClientError(f"grok: {exc}") from exc
