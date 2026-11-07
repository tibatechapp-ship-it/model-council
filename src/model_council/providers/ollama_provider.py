"""Ollama provider for fully local, offline models (``/api/chat``)."""

from __future__ import annotations

import os

import httpx

from model_council.providers.base import CompletionRequest, ModelProvider
from model_council.providers.errors import (
    ProviderRequestError,
    ProviderResponseError,
)

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(ModelProvider):
    name = "ollama"
    label = "Ollama (local models, no API key)"
    env_var = None
    default_model = "llama3.1"
    offline = False

    def __init__(
        self,
        model: str | None = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ):
        super().__init__(model=model, timeout=timeout)
        self.base_url = (
            base_url or os.environ.get("OLLAMA_BASE_URL", "").strip()
            or DEFAULT_BASE_URL
        ).rstrip("/")

    def is_available(self) -> bool:
        """True when an Ollama daemon answers on the configured base URL."""
        try:
            probe = httpx.get(
                f"{self.base_url}/api/version", timeout=min(
                    self.timeout or 5.0, 5.0
                )
            )
        except httpx.HTTPError:
            return False
        return probe.status_code < 500

    def complete(self, request: CompletionRequest) -> str:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens,
                    },
                },
                timeout=self.timeout or 120.0,
            )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                f"Ollama at {self.base_url} unreachable: "
                f"{type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise ProviderRequestError(
                f"Ollama returned HTTP {response.status_code}"
            )
        try:
            content = response.json()["message"]["content"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Ollama response missing message.content."
            ) from exc
        return str(content or "").strip()
