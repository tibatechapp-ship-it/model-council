"""Google Gemini provider (Generative Language API)."""

from __future__ import annotations

import os

from model_council.providers.base import CompletionRequest, ModelProvider
from model_council.providers.errors import ProviderResponseError
from model_council.providers.http import post_json

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


class GoogleProvider(ModelProvider):
    name = "google"
    label = "Google Gemini (generateContent)"
    env_var = "GOOGLE_API_KEY"
    default_model = "gemini-2.0-flash"

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
            base_url or os.environ.get("GOOGLE_BASE_URL", "").strip()
            or DEFAULT_BASE_URL
        ).rstrip("/")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(self, request: CompletionRequest) -> str:
        self.require_available()
        url = (
            f"{self.base_url}/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        data = post_json(
            url,
            headers={"Content-Type": "application/json"},
            payload={
                "systemInstruction": {
                    "parts": [{"text": request.system}],
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": request.user}],
                    },
                ],
                "generationConfig": {
                    "maxOutputTokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            },
            timeout=self.timeout or 60.0,
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(str(p.get("text", "")) for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                "Gemini response missing candidates[0].content.parts."
            ) from exc
        return text.strip()
