from __future__ import annotations

import json
import os
import re
from typing import Protocol, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from src.runtime_config import load_agent_runtime_config


ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredLLM(Protocol):
    def extract_json(self, system_prompt: str, user_prompt: str, schema: type[ModelT]) -> ModelT:
        ...


def require_structured_llm(llm: StructuredLLM | None, capability: str) -> StructuredLLM:
    if llm is None:
        raise RuntimeError(
            f"{capability} requires a configured StructuredLLM. "
            "AGENT_LLM_MODE=off is not supported for full agent graph runs."
        )
    return llm


class OpenRouterStructuredLLM:
    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "deepseek/deepseek-v3.2"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        runtime_config = load_agent_runtime_config()
        openrouter_config = runtime_config.openrouter if runtime_config else None

        token = api_key or (openrouter_config.api_key if openrouter_config else None) or os.getenv("OPENROUTER_API_KEY")
        if not token:
            raise ValueError(
                "OpenRouter API key is required. Set `openrouter.api_key` in "
                "`config/agent_runtime.json` or use `OPENROUTER_API_KEY` as fallback."
            )
        headers = {
            "X-Title": (
                (openrouter_config.app_title if openrouter_config else None)
                or os.getenv("OPENROUTER_APP_TITLE", "Relocation Agent Course Project")
            ),
        }
        http_referer = (
            (openrouter_config.http_referer if openrouter_config else None)
            or os.getenv("OPENROUTER_HTTP_REFERER")
        )
        if http_referer:
            headers["HTTP-Referer"] = http_referer
        self.client = OpenAI(base_url=self.BASE_URL, api_key=token, default_headers=headers)
        self.model = (
            model
            or (openrouter_config.model if openrouter_config else None)
            or os.getenv("OPENROUTER_MODEL", self.DEFAULT_MODEL)
        )

    def extract_json(self, system_prompt: str, user_prompt: str, schema: type[ModelT]) -> ModelT:  # pragma: no cover - network path
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n\nReturn valid JSON only."},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        return schema.model_validate(self._load_json_payload(content))

    @staticmethod
    def _load_json_payload(content: str) -> dict[str, object]:
        text = content.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
            if fenced_match:
                return json.loads(fenced_match.group(1))
            object_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
            if object_match:
                return json.loads(object_match.group(1))
            raise
