"""Provider abstraction layer.

Every council member speaks to the engine through a :class:`ModelProvider`.
A provider turns a :class:`CompletionRequest` into plain text. Providers are
deliberately tiny: they do one HTTPS call (or, for the deterministic test
provider, no call at all) and own no deliberation logic.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field

from model_council.providers.errors import ProviderUnavailableError


class TaskKind(str, Enum):
    """The four phases of the MODEL-COUNCIL deliberation protocol.

    The active task is always stated explicitly in the prompt (``TASK:
    <KIND>``) so that providers - including deterministic test doubles - can
    adapt their output shape without sniffing prose.
    """

    POSITION = "POSITION"
    CRITIQUE = "CRITIQUE"
    REVISE = "REVISE"
    VOTE = "VOTE"


class CompletionRequest(BaseModel):
    """A single completion call issued by the deliberation engine."""

    task: TaskKind
    system: str = ""
    user: str
    max_tokens: int = Field(default=2048, gt=0, le=32768)
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)


class ModelProvider(ABC):
    """Base class for all model providers."""

    #: Short registry name, e.g. ``"openai"``.
    name: str = "abstract"
    #: Human-readable label used by the CLI and API.
    label: str = "Abstract provider"
    #: Environment variable holding the credential, if any.
    env_var: str | None = None
    #: Default model identifier used when the member spec omits one.
    default_model: str = "default"
    #: True when the provider works fully offline (no network, no keys).
    offline: bool = False

    def __init__(self, model: str | None = None, timeout: float | None = None):
        self.model = model or self.default_model
        self.timeout = timeout

    # -- introspection -----------------------------------------------------
    @property
    def configured_model(self) -> str:
        return self.model

    def is_available(self) -> bool:
        """True when the provider can plausibly serve a request."""
        if self.env_var is None:
            return True
        return bool(os.environ.get(self.env_var, "").strip())

    def require_available(self) -> None:
        if not self.is_available():
            raise ProviderUnavailableError(
                f"Provider '{self.name}' is not configured: "
                f"set {self.env_var} or pass an explicit credential."
            )

    # -- completion --------------------------------------------------------
    @abstractmethod
    def complete(self, request: CompletionRequest) -> str:
        """Return the model completion text for ``request``."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} model={self.model!r}>"
