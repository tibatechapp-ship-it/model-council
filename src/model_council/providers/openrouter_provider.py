"""OpenRouter provider (OpenAI-compatible router for many models)."""

from __future__ import annotations

import os

from model_council.providers.base import CompletionRequest, ModelProvider
from model_council.providers.errors import ProviderResponseError
from model_council.providers.http import post_json

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(ModelProvider):
    name = "openrouter"
    label = "OpenRouter (multi-provider router)"
    env_var = "OPENROUTER_API_KEY"
    default_model = "openai/gpt-4o-mini"

    def __init__(
        self,
        model: str | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        super().__init__(model=model, timeout=timeout)
        self.api_key = api_key or os.environ.get(self.env_var, "").strip()
        self.base_url = (
            base_url or os.environ.get("OPENROUTER_BASE_URL", "").strip()
            or DEFAULT_BASE_URL
        ).rstrip("/")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(self, request: CompletionRequest) -> str:
        self.require_available()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = post_json(
            f"{self.base_url}/chat/completions",
            headers=headers,
            payload={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
            timeout=self.timeout or 60.0,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                "OpenRouter response missing choices[0].message.content."
            ) from exc
        return str(content or "").strip()
