"""MODEL-COUNCIL: structured multi-model deliberation.

Quick start::

    from model_council import Council

    council = Council.echo_council()          # offline demo council
    result = council.deliberate("Should we ship feature X on Friday?")
    print(result.winner, result.consensus_score)

With real providers (keys via environment variables)::

    council = Council.from_specs([
        "openai:gpt-4o-mini",
        "anthropic:claude-3-5-haiku-latest",
        "google:gemini-2.0-flash",
    ])
"""

from model_council.engine import (
    Council,
    CouncilMember,
    DeliberationConfig,
    DeliberationResult,
)
from model_council.providers import (
    ProviderRegistry,
    available_providers,
)

__version__ = "20.0.0"

__all__ = [
    "Council",
    "CouncilMember",
    "DeliberationConfig",
    "DeliberationResult",
    "ProviderRegistry",
    "available_providers",
    "__version__",
]
