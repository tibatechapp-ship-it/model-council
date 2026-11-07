"""Request/response payloads of the REST API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from model_council.domain.models import CouncilStatus
from model_council.providers import parse_member_spec


class DeliberationCreateRequest(BaseModel):
    """Body of ``POST /v1/deliberations``.

    ``members`` accepts compact specs such as ``"openai:gpt-4o-mini"``.
    When omitted, the offline demo council is used so the endpoint is
    always callable, even with no provider keys configured.
    """

    question: str = Field(min_length=3, max_length=20000)
    members: list[str] | None = None
    rounds: int = Field(default=1, ge=0, le=5)
    timeout: float = Field(default=60.0, gt=0, le=600)
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0, le=32768)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("members")
    @classmethod
    def validate_members(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("members must not be empty when provided")
        for spec in value:
            try:
                parse_member_spec(spec)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        return value


class DeliberationListEntry(BaseModel):
    council_id: str
    question: str
    status: CouncilStatus
    winner: str | None = None
    consensus_score: float = 0.0
    created_at: datetime
