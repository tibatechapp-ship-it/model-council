"""Shared HTTP plumbing for network providers.

A single ``post_json`` helper with timeout + bounded retry (429/5xx) keeps
the five provider modules small and consistent. Credentials are read from
the environment and are never logged or echoed in errors.
"""

from __future__ import annotations

import time

import httpx

from model_council.providers.errors import (
    ProviderRequestError,
    ProviderResponseError,
)

_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict,
    timeout: float,
    max_retries: int = 2,
) -> dict:
    """POST ``payload`` and return the decoded JSON response.

    Retries idempotency-safe failures (429/5xx) with linear backoff. Raises
    :class:`ProviderRequestError` on transport/HTTP failure and
    :class:`ProviderResponseError` when the body is not decodable JSON.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            last_error = ProviderRequestError(
                f"{url} failed: {type(exc).__name__}"
            )
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:
                    raise ProviderResponseError(
                        f"{url} returned a non-JSON body "
                        f"(status {response.status_code})."
                    ) from exc
            if response.status_code in _RETRYABLE and attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                last_error = ProviderRequestError(
                    f"{url} returned HTTP {response.status_code}"
                )
                continue
            raise ProviderRequestError(
                f"{url} returned HTTP {response.status_code}: "
                f"{_safe_body(response.text)}"
            )
    raise last_error or ProviderRequestError(f"{url} failed")  # pragma: no cover


def _safe_body(text: str, limit: int = 300) -> str:
    """Truncate provider error bodies; they are untrusted input."""
    flat = " ".join(text.split())
    return flat[:limit]
