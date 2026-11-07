"""Anthropic provider (Messages API)."""

from __future__ import annotations

import os

from model_council.providers.base import CompletionRequest, ModelProvider
from model_council.providers.errors import ProviderResponseError
from model_council.providers.http import post_json

DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicProvider(ModelProvider):
    name = "anthropic"
    label = "Anthropic (Messages API)"
    env_var = "ANTHROPIC_API_KEY"
    default_model = "claude-3-5-haiku-latest"

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
            base_url or os.environ.get("ANTHROPIC_BASE_URL", "").strip()
            or DEFAULT_BASE_URL
        ).rstrip("/")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(self, request: CompletionRequest) -> str:
        self.require_available()
        data = post_json(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "system": request.system,
                "messages": [
                    {"role": "user", "content": request.user},
                ],
            },
            timeout=self.timeout or 60.0,
        )
        try:
            blocks = data["content"]
            text = "".join(
                str(block.get("text", "")) for block in blocks
            )
        except (KeyError, TypeError) as exc:
            raise ProviderResponseError(
                "Anthropic response missing content blocks."
            ) from exc
        return text.strip()
