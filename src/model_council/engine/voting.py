"""Weighted Borda voting with transparent tie-breaking.

Rules (documented in docs/PROTOCOL.md):

* A member may **not** vote for itself.
* A ballot ranks other members best-first; the top-ranked member receives
  ``n - 2`` points, the next ``n - 3``, ... down to ``0`` (``n`` = council
  size including the voter).
* Each voter's points are multiplied by the voter's configured ``weight``.
* Ties are broken by similarity to the rest of the council, then by stable
  member order - both deterministic and visible in the result.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from model_council.engine.disagreement import jaccard


class Ballot(BaseModel):
    """One member's ranking of the others' final answers."""

    voter: str
    ranking: list[str] = Field(default_factory=list)
    rationale: str = ""
    counted: bool = True
    note: str | None = None


class VoteTally(BaseModel):
    """Aggregated, weighted Borda result."""

    method: str = "weighted-borda"
    points: dict[str, float] = Field(default_factory=dict)
    weighted_points: dict[str, float] = Field(default_factory=dict)
    winner: str | None = None
    tie_broken: bool = False
    ballots: list[Ballot] = Field(default_factory=list)
    ignored_ballots: int = 0


def tally_votes(
    ballots: list[Ballot],
    *,
    member_order: list[str],
    member_weights: dict[str, float],
    final_answers: dict[str, str] | None = None,
    tie_break_by_consensus: bool = True,
) -> VoteTally:
    """Aggregate ballots into a :class:`VoteTally`."""
    n = len(member_order)
    points = {name: 0.0 for name in member_order}
    weighted = {name: 0.0 for name in member_order}
    ignored = 0

    for ballot in ballots:
        if not ballot.counted:
            ignored += 1
            continue
        weight = member_weights.get(ballot.voter, 1.0)
        for position, candidate in enumerate(ballot.ranking):
            if candidate not in points or candidate == ballot.voter:
                continue
            earned = float(max(n - 2 - position, 0))
            points[candidate] += earned
            weighted[candidate] += earned * weight

    tally = VoteTally(
        points={k: round(v, 3) for k, v in points.items()},
        weighted_points={k: round(v, 3) for k, v in weighted.items()},
        ballots=ballots,
        ignored_ballots=ignored,
    )

    counted_ballots = [b for b in ballots if b.counted]
    if not counted_ballots or n == 0:
        return tally

    best = max(weighted.values())
    leaders = [name for name, v in weighted.items() if v == best]
    if len(leaders) == 1:
        tally.winner = leaders[0]
        return tally

    if tie_break_by_consensus and final_answers:
        consensus = {
            name: _similarity_to_others(name, final_answers)
            for name in leaders
        }
        best_consensus = max(consensus.values())
        leaders = [
            name for name in leaders
            if consensus[name] == best_consensus
        ]
        tally.tie_broken = True

    tally.winner = min(leaders, key=member_order.index)
    return tally


def _similarity_to_others(
    name: str, answers: dict[str, str]
) -> float:
    others = [a for member, a in answers.items() if member != name]
    if not others:
        return 0.0
    own = answers.get(name, "")
    return sum(jaccard(own, other) for other in others) / len(others)
