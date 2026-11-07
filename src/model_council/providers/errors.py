"""Provider-level exceptions.

Providers translate every transport- or credential-level failure into one of
these typed errors so the deliberation engine can degrade gracefully and
report partial results instead of crashing a whole council session.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider failures."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is not configured (missing key, bad URL...)."""


class ProviderRequestError(ProviderError):
    """Raised when a request reaches the provider but fails (4xx/5xx)."""


class ProviderResponseError(ProviderError):
    """Raised when the provider answers but the payload cannot be parsed."""
