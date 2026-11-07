"""Tests for the provider registry, member specs and the echo provider."""

from __future__ import annotations

import pytest

from model_council.engine.council import CouncilMember
from model_council.providers import (
    PROVIDER_CLASSES,
    ProviderRegistry,
    available_providers,
    create_member,
    parse_member_spec,
)
from model_council.providers.base import CompletionRequest, TaskKind
from model_council.providers.echo import EchoProvider
from model_council.providers.errors import ProviderResponseError


def test_registry_contains_all_builtin_providers():
    assert set(PROVIDER_CLASSES) == {
        "echo",
        "openai",
        "anthropic",
        "google",
        "openrouter",
        "ollama",
    }


def test_available_providers_payload():
    items = available_providers()
    by_name = {item["name"]: item for item in items}
    assert by_name["echo"]["available"] is True
    assert by_name["echo"]["offline"] is True
    assert by_name["openai"]["env_var"] == "OPENAI_API_KEY"
    assert by_name["openai"]["available"] is False  # no key in test env


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("echo:optimist", ("echo", "optimist")),
        ("openai:gpt-4o-mini", ("openai", "gpt-4o-mini")),
        ("openrouter:openai/gpt-4o-mini", ("openrouter", "openai/gpt-4o-mini")),
        ("ollama", ("ollama", None)),
    ],
)
def test_parse_member_spec_valid(spec, expected):
    assert parse_member_spec(spec) == expected


def test_parse_member_spec_invalid():
    with pytest.raises(ValueError):
        parse_member_spec("")
    with pytest.raises(ValueError):
        parse_member_spec("  ")


def test_create_member_unknown_provider_fails_eagerly():
    with pytest.raises(KeyError):
        create_member("nosuch:model")


def test_create_member_builds_display_name():
    member = create_member("openai:gpt-4o-mini")
    assert isinstance(member, CouncilMember)
    assert member.provider == "openai"
    assert member.model == "gpt-4o-mini"
    assert member.name == "Gpt 4O Mini"


def test_echo_provider_deterministic():
    provider = EchoProvider(model="optimist")
    request = CompletionRequest(
        task=TaskKind.POSITION,
        user="TASK: POSITION\n\nQUESTION:\nShip or wait?\n",
    )
    first = provider.complete(request)
    second = provider.complete(request)
    assert first == second
    assert "Confidence:" in first


def test_echo_personas_disagree():
    request = CompletionRequest(
        task=TaskKind.POSITION,
        user="TASK: POSITION\n\nQUESTION:\nShip or wait?\n",
    )
    answers = {
        persona: EchoProvider(model=persona).complete(request)
        for persona in ("optimist", "skeptic", "pragmatist")
    }
    assert len(set(answers.values())) == 3


def test_openai_provider_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from model_council.providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider()
    assert provider.is_available() is False


def test_openai_provider_parses_response(monkeypatch):
    from model_council.providers import openai_provider

    captured = {}

    def fake_post(url, *, headers, payload, timeout, max_retries=2):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": " council says yes "}}]}

    monkeypatch.setattr(openai_provider, "post_json", fake_post)
    provider = openai_provider.OpenAIProvider(api_key="test-key")
    text = provider.complete(
        CompletionRequest(task=TaskKind.POSITION, user="hello")
    )
    assert text == "council says yes"
    assert captured["payload"]["model"] == "gpt-4o-mini"
    assert captured["payload"]["messages"][0]["role"] == "system"


def test_openai_provider_raises_on_bad_payload(monkeypatch):
    from model_council.providers import openai_provider

    monkeypatch.setattr(
        openai_provider,
        "post_json",
        lambda *a, **kw: {"unexpected": True},
    )
    provider = openai_provider.OpenAIProvider(api_key="test-key")
    with pytest.raises(ProviderResponseError):
        provider.complete(
            CompletionRequest(task=TaskKind.POSITION, user="hello")
        )


def test_anthropic_provider_parses_blocks(monkeypatch):
    from model_council.providers import anthropic_provider

    monkeypatch.setattr(
        anthropic_provider,
        "post_json",
        lambda *a, **kw: {"content": [{"text": "part1"}, {"text": "part2"}]},
    )
    provider = anthropic_provider.AnthropicProvider(api_key="test-key")
    text = provider.complete(
        CompletionRequest(task=TaskKind.CRITIQUE, user="review this")
    )
    assert text == "part1part2"


def test_google_provider_builds_request(monkeypatch):
    from model_council.providers import google_provider

    captured = {}

    def fake_post(url, *, headers, payload, timeout, max_retries=2):
        captured["url"] = url
        return {
            "candidates": [{"content": {"parts": [{"text": "gemini says"}]}}]
        }

    monkeypatch.setattr(google_provider, "post_json", fake_post)
    provider = google_provider.GoogleProvider(api_key="key", model="gemini-2.0-flash")
    text = provider.complete(
        CompletionRequest(task=TaskKind.REVISE, user="revise")
    )
    assert text == "gemini says"
    assert "gemini-2.0-flash:generateContent" in captured["url"]
    assert "key=key" in captured["url"]


def test_registry_get_unknown_provider_message():
    registry = ProviderRegistry()
    with pytest.raises(KeyError, match="nosuch"):
        registry.get("nosuch")
