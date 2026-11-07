"""Result models of a completed deliberation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from model_council.domain.models import (
    CouncilMode,
    CouncilResult,
    CouncilStatus,
    ModelResponse,
)
from model_council.engine.disagreement import AgreementThemes, DisagreementItem
from model_council.engine.transcript import Phase, Transcript
from model_council.engine.voting import Ballot, VoteTally


class MemberTurn(BaseModel):
    """A member's statement in the POSITION or REVISE phase."""

    member: str
    pseudonym: str
    content: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    round_number: int = 0
    revised: bool = False


class CritiqueTurn(BaseModel):
    """A member's critique of another member's answer."""

    critic: str
    critic_pseudonym: str
    target: str
    target_pseudonym: str
    round_number: int = Field(ge=0)
    content: str


class MemberError(BaseModel):
    """A recorded, non-fatal member failure."""

    member: str
    phase: Phase
    error: str


class DeliberationResult(BaseModel):
    """Everything a council produced for one question.

    The result is intentionally verbose: original positions are preserved
    even after revision, ignored ballots are kept with a reason, and the
    full transcript is embedded so every claim can be audited.
    """

    council_id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    status: CouncilStatus = CouncilStatus.PENDING
    members: list[str] = Field(default_factory=list)
    rounds_requested: int = 0
    rounds_completed: int = 0
    positions: list[MemberTurn] = Field(default_factory=list)
    critiques: list[CritiqueTurn] = Field(default_factory=list)
    revisions: list[MemberTurn] = Field(default_factory=list)
    ballots: list[Ballot] = Field(default_factory=list)
    tally: VoteTally = Field(default_factory=VoteTally)
    winner: str | None = None
    consensus_score: float = Field(default=0.0, ge=0.0, le=1.0)
    agreements: AgreementThemes = Field(default_factory=AgreementThemes)
    disagreements: list[DisagreementItem] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    errors: list[MemberError] = Field(default_factory=list)
    duration_ms: int = Field(default=0, ge=0)
    transcript: Transcript = Field(default_factory=Transcript)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ----------------------------------------------------------- adapters
    def to_council_result(self) -> CouncilResult:
        """Adapter to the legacy ``domain.CouncilResult`` shape."""
        responses = [
            {
                "model": turn.member,
                "provider": "council",
                "content": turn.content,
            }
            for turn in (self.positions + self.revisions)
        ]
        result = CouncilResult(
            council_id=self.council_id,
            question=self.question,
            mode=CouncilMode.DEBATE,
            status=self.status,
            created_at=self.created_at,
        )
        result.responses = [
            ModelResponse(
                model=item["model"],
                provider=item["provider"],
                content=item["content"],
            )
            for item in responses
        ]
        result.agreements = list(self.agreements.themes)
        result.disagreements = [
            f"{item.axis} (severity {item.severity:.2f})"
            for item in self.disagreements
        ]
        result.uncertainties = list(self.uncertainties)
        return result
