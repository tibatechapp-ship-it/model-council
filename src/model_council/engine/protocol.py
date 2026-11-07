"""The four-phase deliberation protocol.

Phases (see docs/PROTOCOL.md for the full specification):

1. POSITION - every member answers the question **independently**; no
   member sees any other member's output.
2. CRITIQUE - each member reviews the *pseudonymised* answers of the
   others, producing per-answer sections and explicit disagreement axes.
3. REVISE - each member revises its own answer in light of the critiques
   it received. Original answers are never overwritten.
4. VOTE - each member ranks the *pseudonymised* final answers; a weighted
   Borda tally picks the council's answer. Self-votes are impossible.

Anonymisation is structural: critique and vote prompts only ever contain
pseudonyms (``Member A`` ...), so popularity of a brand cannot bias
cross-review. Failures are non-fatal: a member that errors out is recorded
and excluded from later phases, and the session continues (status PARTIAL).
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from model_council.domain.models import CouncilStatus
from model_council.engine.config import DeliberationConfig
from model_council.engine.disagreement import (
    analyze_disagreements,
    common_themes,
    jaccard,
)
from model_council.engine.results import (
    CritiqueTurn,
    DeliberationResult,
    MemberError,
    MemberTurn,
)
from model_council.engine.transcript import Phase, Transcript
from model_council.engine.voting import Ballot, tally_votes
from model_council.providers.base import CompletionRequest, ModelProvider, TaskKind

PSEUDONYMS = "ABCDEFGHIJ"
MAX_EMBED_CHARS = 6000

_BALLOT_RE = re.compile(r"BALLOT:\s*([A-Z](?:\s*,\s*[A-Z])*\.?)", re.I)
_RATIONALE_RE = re.compile(r"RATIONALE:\s*(.+)", re.I)
_CONFIDENCE_RE = re.compile(r"Confidence:\s*(\d{1,2})\s*/\s*10", re.I)
_SECTION_RE = re.compile(r"^\[Member ([A-Z])\]\s*$", re.M)
_AXES_RE = re.compile(
    r"KEY DISAGREEMENTS:\s*\n((?:\s*[-*].+\n?)+)", re.I
)


# --------------------------------------------------------------------------
# Prompt builders
# --------------------------------------------------------------------------
def position_system(member_name: str, custom: str | None) -> str:
    if custom:
        return custom
    return (
        f"You are {member_name}, an independent member of an AI model "
        "council. Reason with your own judgement; do not guess what other "
        "members might say. Be concrete, weigh evidence, and state "
        "uncertainty explicitly. End with a final line 'Confidence: X/10'."
    )


def position_prompt(question: str) -> str:
    return (
        f"TASK: {TaskKind.POSITION.value}\n\n"
        f"QUESTION:\n{question}\n\n"
        "Respond with your independent position. End with "
        "'Confidence: X/10'."
    )


def critique_prompt(
    question: str, pseudonymised_answers: list[tuple[str, str]]
) -> str:
    blocks = "\n\n".join(
        f"[Member {pseudo}]\n{_clip(answer)}"
        for pseudo, answer in pseudonymised_answers
    )
    return (
        f"TASK: {TaskKind.CRITIQUE.value}\n\n"
        f"QUESTION:\n{question}\n\n"
        "ANSWERS FROM OTHER MEMBERS (anonymised):\n"
        f"{blocks}\n\n"
        "For EACH answer above, produce a section that starts with its "
        "[Member X] header and covers: Strengths, Weaknesses, Factual or "
        "logical risks, Missing considerations.\n"
        "Then end with a final section:\n"
        "KEY DISAGREEMENTS:\n- <one line per axis where the answers "
        "diverge>"
    )


def revise_prompt(
    question: str, original: str, critiques_received: list[str]
) -> str:
    received = "\n\n".join(f"- {_clip(c)}" for c in critiques_received)
    if not received.strip("- "):
        received = "- No critiques were received."
    return (
        f"TASK: {TaskKind.REVISE.value}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"YOUR ORIGINAL ANSWER:\n{_clip(original)}\n\n"
        f"CRITIQUES RECEIVED:\n{received}\n\n"
        "Revise your answer: keep claims that survive scrutiny, fix what "
        "was correctly criticised, and state what remains uncertain. End "
        "with 'Confidence: X/10'."
    )


def vote_prompt(
    question: str, pseudonymised_finals: list[tuple[str, str]]
) -> str:
    blocks = "\n\n".join(
        f"[Member {pseudo}]\n{_clip(answer)}" for pseudo, answer in pseudonymised_finals
    )
    return (
        f"TASK: {TaskKind.VOTE.value}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"FINAL ANSWERS (anonymised):\n{blocks}\n\n"
        "Rank ONLY the other members' answers from best to worst by "
        "correctness, evidence quality and robustness. Do not rank your "
        "own answer. Output exactly:\n"
        "BALLOT: <letters, best first, comma-separated>\n"
        "RATIONALE: <one line>"
    )


def _clip(text: str, limit: int = MAX_EMBED_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[...truncated...]"


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------
def parse_confidence(text: str) -> float | None:
    match = _CONFIDENCE_RE.search(text)
    if not match:
        return None
    return min(int(match.group(1)), 10) / 10.0


def parse_ballot(
    text: str, valid_letters: dict[str, str]
) -> tuple[list[str], str]:
    """Parse a BALLOT block into ranked member names."""
    match = _BALLOT_RE.search(text)
    if not match:
        return [], ""
    letters = re.findall(r"[A-Z]", match.group(1).upper())
    ranking: list[str] = []
    for letter in letters:
        if letter in valid_letters:
            name = valid_letters[letter]
            if name not in ranking:
                ranking.append(name)
    rationale_match = _RATIONALE_RE.search(text)
    rationale = rationale_match.group(1).strip() if rationale_match else ""
    return ranking, rationale


def parse_critique_sections(
    text: str, target_letters: dict[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Split a critique into ``{letter: section}`` plus disagreement axes."""
    matches = list(_SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        letter = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if letter in target_letters:
            sections[letter] = body

    axes: list[str] = []
    axes_match = _AXES_RE.search(text)
    if axes_match:
        for line in axes_match.group(1).splitlines():
            line = line.strip().lstrip("-*").strip()
            if line:
                axes.append(line)
    return sections, axes


# --------------------------------------------------------------------------
# Runtime member
# --------------------------------------------------------------------------
class ActiveMember:
    """A council member with its provider resolved and live state."""

    def __init__(self, name: str, provider: ModelProvider, weight: float,
                 system_prompt: str | None) -> None:
        self.name = name
        self.provider = provider
        self.weight = weight
        self.system_prompt = system_prompt
        self.pseudonym = ""
        self.failed = False
        self.latest: str = ""
        self.original: str = ""
        self.confidence: float | None = None

    @property
    def letter(self) -> str:
        return self.pseudonym.removeprefix("Member ").strip()


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
class ProtocolRunner:
    """Executes the four-phase protocol and assembles the result."""

    def __init__(
        self,
        members: list,
        config: DeliberationConfig | None = None,
        registry=None,
    ):
        from model_council.providers import ProviderRegistry

        self.config = config or DeliberationConfig()
        self.registry = registry or ProviderRegistry()
        self.members: list[ActiveMember] = []
        for index, member in enumerate(members):
            provider = self.registry.get(
                member.provider,
                model=member.model,
                timeout=self.config.timeout,
            )
            active = ActiveMember(
                name=member.name,
                provider=provider,
                weight=member.weight,
                system_prompt=member.system_prompt,
            )
            active.pseudonym = (
                f"Member {PSEUDONYMS[index]}" if index < len(PSEUDONYMS)
                else f"Member {index + 1}"
            )
            self.members.append(active)

    # ----------------------------------------------------------------- run
    def run(self, question: str) -> DeliberationResult:
        started = time.monotonic()
        transcript = Transcript()
        errors: list[MemberError] = []
        transcript.add_system_note(
            "Session started with members: "
            + ", ".join(
                f"{m.name} ({m.pseudonym})" for m in self.members
            )
        )

        positions = self._run_position(question, transcript, errors)
        rounds_completed = 0
        all_critiques: list[CritiqueTurn] = []
        reported_axes: list[tuple[str, str, str]] = []

        for round_number in range(1, self.config.rounds + 1):
            if self._active_count() < 2:
                transcript.add_system_note(
                    "Critique skipped: fewer than two active members remain."
                )
                break
            critiques, axes = self._run_critique(
                question, round_number, transcript, errors
            )
            all_critiques.extend(critiques)
            reported_axes.extend(axes)
            self._run_revise(
                question, round_number, critiques, transcript, errors
            )
            rounds_completed = round_number

        ballots = self._run_vote(question, transcript, errors)
        finals = {m.name: m.latest for m in self.members if not m.failed and m.latest}

        tally = tally_votes(
            ballots,
            member_order=[m.name for m in self.members if not m.failed],
            member_weights={m.name: m.weight for m in self.members},
            final_answers=finals,
            tie_break_by_consensus=self.config.tie_break_by_consensus,
        )
        consensus = self._consensus(finals)
        disagreements = analyze_disagreements(
            finals,
            cluster_threshold=self.config.cluster_threshold,
            reported_axes=reported_axes,
        )
        agreements = common_themes(finals)
        uncertainties = self._uncertainties(finals)

        if not finals:
            status = CouncilStatus.FAILED
        elif errors:
            status = CouncilStatus.PARTIAL
        else:
            status = CouncilStatus.COMPLETED

        duration_ms = int((time.monotonic() - started) * 1000)
        return DeliberationResult(
            question=question,
            status=status,
            members=[m.name for m in self.members],
            rounds_requested=self.config.rounds,
            rounds_completed=rounds_completed,
            positions=positions,
            critiques=all_critiques,
            revisions=[
                MemberTurn(
                    member=m.name,
                    pseudonym=m.pseudonym,
                    content=m.latest,
                    confidence=m.confidence,
                    round_number=self.config.rounds,
                    revised=True,
                )
                for m in self.members
                if not m.failed and m.original and m.latest != m.original
            ],
            ballots=ballots,
            tally=tally,
            winner=tally.winner,
            consensus_score=consensus,
            agreements=agreements,
            disagreements=disagreements,
            uncertainties=uncertainties,
            errors=errors,
            duration_ms=duration_ms,
            transcript=transcript,
        )

    # ------------------------------------------------------------- helpers
    def _active(self) -> list[ActiveMember]:
        return [m for m in self.members if not m.failed]

    def _active_count(self) -> int:
        return len(self._active())

    def _run_position(
        self, question: str, transcript: Transcript, errors: list[MemberError]
    ) -> list[MemberTurn]:
        transcript.add_system_note(
            f"Phase 1 - POSITION: {self._active_count()} members answer "
            "independently; no member sees another member's output."
        )
        prompts = {
            m: CompletionRequest(
                task=TaskKind.POSITION,
                system=position_system(m.name, m.system_prompt),
                user=position_prompt(question),
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            for m in self._active()
        }
        outputs = self._call_providers(prompts, transcript, errors, Phase.POSITION)
        turns: list[MemberTurn] = []
        for member, text in outputs.items():
            member.original = text
            member.latest = text
            member.confidence = parse_confidence(text)
            turns.append(
                MemberTurn(
                    member=member.name,
                    pseudonym=member.pseudonym,
                    content=text,
                    confidence=member.confidence,
                )
            )
            transcript.add(
                Phase.POSITION, member.name, text, pseudonym=member.pseudonym
            )
        return turns

    def _run_critique(
        self,
        question: str,
        round_number: int,
        transcript: Transcript,
        errors: list[MemberError],
    ) -> tuple[list[CritiqueTurn], list[tuple[str, str, str]]]:
        critics = self._active()
        prompts: dict[ActiveMember, CompletionRequest] = {}
        targets_by_critic: dict[ActiveMember, dict[str, ActiveMember]] = {}

        for critic in critics:
            others = [m for m in critics if m is not critic]
            pairs = [(m.letter, m.latest) for m in others]
            targets_by_critic[critic] = {m.letter: m for m in others}
            prompts[critic] = CompletionRequest(
                task=TaskKind.CRITIQUE,
                system=position_system(critic.name, critic.system_prompt),
                user=critique_prompt(question, pairs),
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

        outputs = self._call_providers(
            prompts, transcript, errors, Phase.CRITIQUE, round_number
        )
        turns: list[CritiqueTurn] = []
        axes: list[tuple[str, str, str]] = []
        for critic, text in outputs.items():
            transcript.add(
                Phase.CRITIQUE,
                critic.name,
                text,
                round_number=round_number,
                pseudonym=critic.pseudonym,
            )
            letters = {
                letter: other.pseudonym
                for letter, other in targets_by_critic[critic].items()
            }
            sections, critic_axes = parse_critique_sections(text, letters)
            for letter, section in sections.items():
                target = targets_by_critic[critic][letter]
                turns.append(
                    CritiqueTurn(
                        critic=critic.name,
                        critic_pseudonym=critic.pseudonym,
                        target=target.name,
                        target_pseudonym=target.pseudonym,
                        round_number=round_number,
                        content=section,
                    )
                )
            for axis in critic_axes:
                for letter in letters:
                    target = targets_by_critic[critic][letter]
                    axes.append((critic.name, target.name, axis))
        return turns, axes

    def _run_revise(
        self,
        question: str,
        round_number: int,
        critiques: list[CritiqueTurn],
        transcript: Transcript,
        errors: list[MemberError],
    ) -> None:
        members = self._active()
        prompts: dict[ActiveMember, CompletionRequest] = {}
        received_by_member: dict[ActiveMember, list[str]] = {}
        for member in members:
            received = [
                c.content
                for c in critiques
                if c.target == member.name and c.round_number == round_number
            ]
            received_by_member[member] = received
            prompts[member] = CompletionRequest(
                task=TaskKind.REVISE,
                system=position_system(member.name, member.system_prompt),
                user=revise_prompt(question, member.latest, received),
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

        outputs = self._call_providers(
            prompts, transcript, errors, Phase.REVISE, round_number
        )
        for member, text in outputs.items():
            member.latest = text
            confidence = parse_confidence(text)
            if confidence is not None:
                member.confidence = confidence
            transcript.add(
                Phase.REVISE,
                member.name,
                text,
                round_number=round_number,
                pseudonym=member.pseudonym,
            )

    def _run_vote(
        self, question: str, transcript: Transcript, errors: list[MemberError]
    ) -> list[Ballot]:
        voters = self._active()
        if len(voters) < 2:
            transcript.add_system_note(
                "Vote skipped: fewer than two active members remain; no "
                "winner is declared."
            )
            return []
        prompts: dict[ActiveMember, CompletionRequest] = {}
        others_by_voter: dict[ActiveMember, dict[str, ActiveMember]] = {}
        for voter in voters:
            others = [m for m in voters if m is not voter]
            others_by_voter[voter] = {m.letter: m for m in others}
            prompts[voter] = CompletionRequest(
                task=TaskKind.VOTE,
                system=position_system(voter.name, voter.system_prompt),
                user=vote_prompt(
                    question, [(m.letter, m.latest) for m in others]
                ),
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

        outputs = self._call_providers(prompts, transcript, errors, Phase.VOTE)
        ballots: list[Ballot] = []
        for voter, text in outputs.items():
            letters = {
                letter: other.name
                for letter, other in others_by_voter[voter].items()
            }
            ranking, rationale = parse_ballot(text, letters)
            counted = bool(ranking)
            ballot = Ballot(
                voter=voter.name,
                ranking=ranking,
                rationale=rationale,
                counted=counted,
                note=None if counted else "No parsable BALLOT block.",
            )
            ballots.append(ballot)
            transcript.add(
                Phase.VOTE,
                voter.name,
                text,
                pseudonym=voter.pseudonym,
                counted=str(counted),
            )
        return ballots

    def _call_providers(
        self,
        prompts: dict,
        transcript: Transcript,
        errors: list[MemberError],
        phase: Phase,
        round_number: int = 0,
    ) -> dict:
        """Run provider calls in parallel, preserving member order."""
        if not prompts:
            return {}
        results: dict = {}
        members = list(prompts)
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            futures = {
                pool.submit(self._safe_complete, member, prompts[member]): member
                for member in members
            }
            for future, member in futures.items():
                try:
                    results[member] = future.result()
                except Exception as exc:  # noqa: BLE001 - boundary
                    member.failed = True
                    message = f"{type(exc).__name__}: {exc}"
                    errors.append(
                        MemberError(
                            member=member.name, phase=phase, error=message
                        )
                    )
                    transcript.add_system_note(
                        f"{member.name} failed in {phase.value} "
                        f"(round {round_number or '-'}): {message}"
                    )
        return results

    @staticmethod
    def _safe_complete(member: ActiveMember, request: CompletionRequest) -> str:
        text = member.provider.complete(request).strip()
        if not text:
            raise ValueError("Provider returned an empty completion.")
        return text

    @staticmethod
    def _consensus(finals: dict[str, str]) -> float:
        names = sorted(finals)
        if len(names) <= 1:
            return 1.0 if names else 0.0
        pairs = [
            jaccard(finals[a], finals[b])
            for i, a in enumerate(names)
            for b in names[i + 1:]
        ]
        return round(sum(pairs) / len(pairs), 3)

    @staticmethod
    def _uncertainties(finals: dict[str, str]) -> list[str]:
        items: list[str] = []
        for name in sorted(finals):
            text = finals[name]
            confidence = parse_confidence(text)
            if confidence is not None and confidence <= 0.6:
                items.append(
                    f"{name} reports low confidence ({int(confidence * 10)}/10)."
                )
            for line in text.splitlines():
                if line.strip().lower().startswith(
                    ("caveat:", "uncertain", "uncertainty:")
                ):
                    items.append(f"{name}: {line.strip()}")
        return items
