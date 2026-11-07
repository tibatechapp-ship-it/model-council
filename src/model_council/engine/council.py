"""Public facade of the deliberation engine.

``Council`` is the one class most users need::

    from model_council import Council, CouncilMember

    council = Council.from_specs(["echo:optimist", "echo:skeptic"])
    result = council.deliberate("Should we migrate the billing service?")
    print(result.winner, result.consensus_score)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from model_council.engine.config import DeliberationConfig
from model_council.engine.protocol import ProtocolRunner
from model_council.providers import ProviderRegistry, create_member

if TYPE_CHECKING:  # pragma: no cover
    from model_council.engine.results import DeliberationResult

_DEFAULT_ECHO_COUNCIL = [
    "echo:optimist",
    "echo:skeptic",
    "echo:pragmatist",
]


class CouncilMember:
    """One seat in the council.

    Prefer :meth:`Council.from_specs` for compact construction;
    ``CouncilMember`` gives full control (explicit names, weights and
    custom system prompts).
    """

    def __init__(
        self,
        name: str,
        provider: str,
        model: str | None = None,
        weight: float = 1.0,
        system_prompt: str | None = None,
    ):
        if not name.strip():
            raise ValueError("Member name must not be empty.")
        if weight <= 0:
            raise ValueError("Member weight must be positive.")
        self.name = name.strip()
        self.provider = provider
        self.model = model
        self.weight = weight
        self.system_prompt = system_prompt

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        model = f", model={self.model!r}" if self.model else ""
        return f"CouncilMember({self.name!r}, provider={self.provider!r}{model})"


class Council:
    """A deliberating body of independent model members."""

    def __init__(
        self,
        members: list[CouncilMember],
        config: DeliberationConfig | None = None,
        registry: ProviderRegistry | None = None,
    ):
        if not members:
            raise ValueError("A council needs at least one member.")
        self.members = _dedupe_names(members)
        self.config = config or DeliberationConfig()
        self.registry = registry

    # ------------------------------------------------------------ builders
    @classmethod
    def from_specs(
        cls,
        specs: list[str],
        config: DeliberationConfig | None = None,
    ) -> Council:
        """Build a council from compact member specs (``provider:model``)."""
        if not specs:
            raise ValueError("A council needs at least one member spec.")
        members = [create_member(spec) for spec in specs]
        return cls(members=members, config=config)

    @classmethod
    def echo_council(
        cls, config: DeliberationConfig | None = None
    ) -> Council:
        """The built-in offline demo council (no API keys required)."""
        return cls.from_specs(_DEFAULT_ECHO_COUNCIL, config=config)

    # ----------------------------------------------------------------- run
    def deliberate(self, question: str) -> DeliberationResult:
        """Run the full four-phase protocol on ``question``."""
        question = question.strip()
        if len(question) < 3:
            raise ValueError("Question must be at least 3 characters long.")
        runner = ProtocolRunner(
            members=self.members,
            config=self.config,
            registry=self.registry,
        )
        result: DeliberationResult = runner.run(question)
        return result


def _dedupe_names(members: list[CouncilMember]) -> list[CouncilMember]:
    seen: dict[str, int] = {}
    unique: list[CouncilMember] = []
    for member in members:
        count = seen.get(member.name, 0)
        seen[member.name] = count + 1
        if count:
            member = CouncilMember(
                name=f"{member.name} {count + 1}",
                provider=member.provider,
                model=member.model,
                weight=member.weight,
                system_prompt=member.system_prompt,
            )
        unique.append(member)
    return unique
