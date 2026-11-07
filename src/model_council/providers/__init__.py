"""Provider registry and member-spec parsing.

A *member spec* is a compact string that identifies a council member:

    echo:optimist                     -> EchoProvider with persona "optimist"
    openai:gpt-4o-mini                -> OpenAIProvider, model gpt-4o-mini
    anthropic:claude-3-5-haiku-latest
    google:gemini-2.0-flash
    openrouter:openai/gpt-4o-mini
    ollama:llama3.1                   -> local model via Ollama
    openai                            -> provider with its default model

The registry is the single place that maps names to provider classes, so
adding a provider means adding one module and one line here.
"""

from __future__ import annotations

from model_council.providers.base import ModelProvider
from model_council.providers.echo import EchoProvider

PROVIDER_CLASSES: dict[str, type[ModelProvider]] = {
    "echo": EchoProvider,
}


def register_provider(provider_cls: type[ModelProvider]) -> None:
    """Register a provider class under its ``name``."""
    PROVIDER_CLASSES[provider_cls.name] = provider_cls


def _load_network_providers() -> None:
    """Import HTTP providers lazily so offline use stays dependency-light."""
    # httpx is a hard dependency of the package, so a plain import is fine;
    # the lazy import only keeps module import order predictable in tests.
    from model_council.providers.anthropic_provider import AnthropicProvider
    from model_council.providers.google_provider import GoogleProvider
    from model_council.providers.ollama_provider import OllamaProvider
    from model_council.providers.openai_provider import OpenAIProvider
    from model_council.providers.openrouter_provider import (
        OpenRouterProvider,
    )

    for cls in (
        OpenAIProvider,
        AnthropicProvider,
        GoogleProvider,
        OpenRouterProvider,
        OllamaProvider,
    ):
        register_provider(cls)


_load_network_providers()


class ProviderRegistry:
    """Thin, testable facade over the module-level registry."""

    def names(self) -> list[str]:
        return sorted(PROVIDER_CLASSES)

    def classes(self) -> dict[str, type[ModelProvider]]:
        return dict(PROVIDER_CLASSES)

    def get(self, name: str, **kwargs) -> ModelProvider:
        try:
            cls = PROVIDER_CLASSES[name]
        except KeyError:
            known = ", ".join(self.names())
            raise KeyError(
                f"Unknown provider '{name}'. Known providers: {known}"
            ) from None
        return cls(**kwargs)


def parse_member_spec(spec: str) -> tuple[str, str | None]:
    """Split ``provider[:model]`` into ``(provider, model_or_None)``."""
    spec = spec.strip()
    if not spec:
        raise ValueError("Member spec must not be empty.")
    if ":" in spec:
        provider, model = spec.split(":", 1)
        provider, model = provider.strip(), model.strip()
        if not provider:
            raise ValueError(f"Invalid member spec: {spec!r}")
        return provider, model or None
    return spec, None


def create_member(spec: str, name: str | None = None, weight: float = 1.0):
    """Build a :class:`~model_council.engine.council.CouncilMember`.

    Raises ``KeyError`` eagerly when the provider name is unknown, so bad
    specs fail before any deliberation work starts.
    """
    from model_council.engine.council import CouncilMember

    provider_name, model = parse_member_spec(spec)
    if provider_name not in PROVIDER_CLASSES:
        known = ", ".join(sorted(PROVIDER_CLASSES))
        raise KeyError(
            f"Unknown provider '{provider_name}'. Known providers: {known}"
        )
    display = name or _display_name(spec)
    return CouncilMember(
        name=display,
        provider=provider_name,
        model=model,
        weight=weight,
    )


def _display_name(spec: str) -> str:
    provider, model = parse_member_spec(spec)
    if model:
        tail = model.rsplit("/", 1)[-1]
        return tail.replace("-", " ").replace("_", " ").title()
    return provider.title()


def available_providers() -> list[dict]:
    """Introspection payload used by the CLI and the REST API."""
    items: list[dict] = []
    for name in sorted(PROVIDER_CLASSES):
        cls = PROVIDER_CLASSES[name]
        probe = cls()
        items.append(
            {
                "name": name,
                "label": cls.label,
                "env_var": cls.env_var,
                "default_model": cls.default_model,
                "offline": cls.offline,
                "available": probe.is_available(),
            }
        )
    return items
