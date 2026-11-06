from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class CouncilMode(str, Enum):
    PARALLEL = "parallel"
    DEBATE = "debate"
    VERIFICATION = "verification"


class CouncilStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class CouncilRequest(BaseModel):
    question: str = Field(min_length=3, max_length=20000)
    mode: CouncilMode = CouncilMode.PARALLEL
    models: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    model: str
    provider: str
    content: str
    success: bool = True
    error: str | None = None
    duration_ms: int | None = None


class CouncilResult(BaseModel):
    council_id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    mode: CouncilMode
    status: CouncilStatus = CouncilStatus.PENDING
    responses: list[ModelResponse] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
