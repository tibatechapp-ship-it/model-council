from datetime import timezone

import pytest
from pydantic import ValidationError

from model_council.domain.models import (
    CouncilMode,
    CouncilRequest,
    CouncilResult,
    CouncilStatus,
    ModelResponse,
)


def test_request_defaults():
    request = CouncilRequest(question="Evaluate this architecture")
    assert request.mode == CouncilMode.PARALLEL
    assert request.models == []
    assert request.metadata == {}


def test_request_accepts_debate_mode():
    request = CouncilRequest(
        question="Compare these approaches",
        mode=CouncilMode.DEBATE,
    )
    assert request.mode == CouncilMode.DEBATE


def test_request_rejects_short_question():
    with pytest.raises(ValidationError):
        CouncilRequest(question="Hi")


def test_request_rejects_excessively_long_question():
    with pytest.raises(ValidationError):
        CouncilRequest(question="x" * 20001)


def test_model_response_defaults():
    response = ModelResponse(
        model="example-model",
        provider="example",
        content="A response",
    )
    assert response.success is True
    assert response.error is None
    assert response.duration_ms is None


def test_council_results_have_unique_ids():
    first = CouncilResult(
        question="Question one",
        mode=CouncilMode.PARALLEL,
    )
    second = CouncilResult(
        question="Question two",
        mode=CouncilMode.PARALLEL,
    )
    assert first.council_id != second.council_id


def test_council_result_defaults():
    result = CouncilResult(
        question="Test question",
        mode=CouncilMode.VERIFICATION,
    )
    assert result.status == CouncilStatus.PENDING
    assert result.responses == []
    assert result.agreements == []
    assert result.disagreements == []
    assert result.uncertainties == []
    assert result.created_at.tzinfo == timezone.utc
