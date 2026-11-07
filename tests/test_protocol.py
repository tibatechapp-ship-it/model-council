"""End-to-end protocol tests on the deterministic echo council."""

from __future__ import annotations

import pytest

from model_council.domain.models import CouncilStatus
from model_council.engine import Council, DeliberationConfig
from model_council.engine.council import CouncilMember
from model_council.engine.protocol import (
    critique_prompt,
    parse_ballot,
    parse_confidence,
    parse_critique_sections,
    position_prompt,
    vote_prompt,
)
from model_council.engine.results import DeliberationResult
from model_council.providers.base import CompletionRequest, ModelProvider

ECHO_SPECS = ["echo:optimist", "echo:skeptic", "echo:pragmatist"]
QUESTION = "Should the team ship the feature on Friday?"


def _run(rounds: int = 1) -> DeliberationResult:
    council = Council.from_specs(ECHO_SPECS, config=DeliberationConfig(rounds=rounds))
    return council.deliberate(QUESTION)


class _ExplodingProvider(ModelProvider):
    name = "exploding"
    label = "always fails"
    default_model = "boom"

    def complete(self, request: CompletionRequest) -> str:
        raise RuntimeError("provider is down")


@pytest.fixture()
def exploding_registry():
    from model_council.providers import ProviderRegistry, register_provider

    register_provider(_ExplodingProvider)
    yield ProviderRegistry()
    PROVIDER_CLASSES_CLEANUP = "exploding"
    from model_council.providers import PROVIDER_CLASSES

    PROVIDER_CLASSES.pop(PROVIDER_CLASSES_CLEANUP, None)


def test_full_deliberation_completes():
    result = _run(rounds=1)
    assert result.status == CouncilStatus.COMPLETED
    assert len(result.positions) == 3
    assert len(result.critiques) == 6  # 3 critics x 2 targets
    assert len(result.revisions) == 3
    assert len(result.ballots) == 3
    assert all(ballot.counted for ballot in result.ballots)
    assert result.winner is not None
    assert 0.0 <= result.consensus_score <= 1.0
    assert result.rounds_completed == 1
    assert result.duration_ms >= 0
    assert result.errors == []


def test_positions_are_preserved_after_revision():
    result = _run(rounds=1)
    originals = {turn.member: turn.content for turn in result.positions}
    assert result.revisions, "echo council always produces revisions"
    for revision in result.revisions:
        assert originals[revision.member]  # original kept verbatim
        assert revision.revised is True


def test_pseudonyms_assigned_in_order():
    result = _run(rounds=0)
    pseudonyms = {turn.pseudonym for turn in result.positions}
    assert pseudonyms == {"Member A", "Member B", "Member C"}


def test_transcript_renders_all_phases():
    result = _run(rounds=1)
    markdown = result.transcript.render_markdown(result.question)
    assert "# MODEL-COUNCIL Deliberation Transcript" in markdown
    assert "## Phase: POSITION" in markdown
    assert "## Phase: CRITIQUE - Round 1" in markdown
    assert "## Phase: REVISE - Round 1" in markdown
    assert "## Phase: VOTE" in markdown


def test_zero_rounds_skips_critique_and_revision():
    result = _run(rounds=0)
    assert result.critiques == []
    assert result.revisions == []
    assert len(result.ballots) == 3
    assert result.rounds_completed == 0


def test_member_failure_degrades_to_partial(exploding_registry):
    members = [
        CouncilMember(name="Broken", provider="exploding"),
        CouncilMember(name="Optimist", provider="echo", model="optimist"),
        CouncilMember(name="Skeptic", provider="echo", model="skeptic"),
    ]
    council = Council(
        members=members,
        config=DeliberationConfig(rounds=1),
        registry=exploding_registry,
    )
    result = council.deliberate(QUESTION)
    assert result.status == CouncilStatus.PARTIAL
    assert len(result.errors) >= 1
    assert result.errors[0].member == "Broken"
    assert result.winner is not None  # survivors still produce a verdict
    remaining = set(result.members) - {"Broken"}
    assert remaining


def test_all_members_failing_marks_failed(exploding_registry):
    members = [
        CouncilMember(name="Broken 1", provider="exploding"),
        CouncilMember(name="Broken 2", provider="exploding"),
    ]
    council = Council(
        members=members,
        config=DeliberationConfig(rounds=0),
        registry=exploding_registry,
    )
    result = council.deliberate(QUESTION)
    assert result.status == CouncilStatus.FAILED
    assert result.winner is None


def test_prompts_are_pseudonymised():
    answers = [("B", "Answer from B"), ("C", "Answer from C")]
    prompt = critique_prompt(QUESTION, answers)
    assert "[Member B]" in prompt
    assert "[Member C]" in prompt
    assert "optimist" not in prompt.lower()

    vote = vote_prompt(QUESTION, answers)
    assert "[Member B]" in vote
    assert "BALLOT:" in vote

    position = position_prompt(QUESTION)
    assert position.startswith("TASK: POSITION")


def test_parse_confidence():
    assert parse_confidence("stuff\nConfidence: 8/10") == 0.8
    assert parse_confidence("Confidence: 12/10") == 1.0
    assert parse_confidence("no confidence line") is None


def test_parse_ballot_dedupes_and_validates():
    letters = {"A": "Ann", "B": "Bob", "C": "Cid"}
    ranking, rationale = parse_ballot(
        "BALLOT: B, A, B, Q\nRATIONALE: quality first", letters
    )
    assert ranking == ["Bob", "Ann"]
    assert rationale == "quality first"

    ranking_empty, _ = parse_ballot("no ballot here", letters)
    assert ranking_empty == []


def test_parse_critique_sections():
    text = (
        "[Member B]\nStrengths: clear.\nWeaknesses: none noted.\n\n"
        "[Member C]\nStrengths: honest.\n\n"
        "KEY DISAGREEMENTS:\n- timing of the release\n- tail risk"
    )
    sections, axes = parse_critique_sections(text, {"B": "pB", "C": "pC"})
    assert set(sections) == {"B", "C"}
    assert "clear" in sections["B"]
    assert axes == ["timing of the release", "tail risk"]


def test_duplicate_member_names_are_deduplicated():
    council = Council.from_specs(["echo:optimist", "echo:optimist"])
    names = [member.name for member in council.members]
    assert len(set(names)) == 2
    assert names[0] != names[1]


def test_council_requires_members_and_question():
    with pytest.raises(ValueError):
        Council.from_specs([])
    council = Council.from_specs(["echo:optimist"])
    with pytest.raises(ValueError):
        council.deliberate("hi")


def test_to_council_result_legacy_adapter():
    result = _run(rounds=1)
    legacy = result.to_council_result()
    assert legacy.council_id == result.council_id
    assert legacy.mode.value == "debate"
    assert legacy.status == CouncilStatus.COMPLETED
    assert legacy.responses
    assert legacy.disagreements
