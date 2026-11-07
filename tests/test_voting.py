"""Tests for weighted Borda voting and tie-breaking."""

from __future__ import annotations

from model_council.engine.voting import Ballot, tally_votes


def _ballots() -> list[Ballot]:
    return [
        Ballot(voter="A", ranking=["B", "C"], rationale="r"),
        Ballot(voter="B", ranking=["A", "C"], rationale="r"),
        Ballot(voter="C", ranking=["A", "B"], rationale="r"),
    ]


def test_borda_points_basic():
    tally = tally_votes(
        _ballots(),
        member_order=["A", "B", "C"],
        member_weights={"A": 1.0, "B": 1.0, "C": 1.0},
    )
    # n=3: first rank earns 1 point, second earns 0.
    assert tally.points == {"A": 2.0, "B": 1.0, "C": 0.0}
    assert tally.winner == "A"
    assert tally.tie_broken is False
    assert tally.ignored_ballots == 0


def test_weights_multiply_voter_points():
    ballots = [
        Ballot(voter="A", ranking=["B", "C"]),
        Ballot(voter="B", ranking=["A", "C"]),
        Ballot(voter="C", ranking=["A", "B"]),
    ]
    tally = tally_votes(
        ballots,
        member_order=["A", "B", "C"],
        member_weights={"A": 1.0, "B": 3.0, "C": 1.0},
    )
    # B's ballot carries triple weight: A gets 1 + 3*1 = 4.
    assert tally.weighted_points["A"] == 4.0
    assert tally.winner == "A"


def test_self_votes_and_unknown_candidates_are_skipped():
    ballots = [
        # A's ballot: self and unknown candidate are skipped; B sits at
        # position 2 and earns max(3-2-2, 0) = 0 points.
        Ballot(voter="A", ranking=["A", "Z", "B"]),
        # B's ballot: A sits at position 0 and earns 3-2-0 = 1 point.
        Ballot(voter="B", ranking=["A"]),
    ]
    tally = tally_votes(
        ballots,
        member_order=["A", "B", "C"],
        member_weights={"A": 1.0, "B": 1.0, "C": 1.0},
    )
    assert tally.points == {"A": 1.0, "B": 0.0, "C": 0.0}


def test_two_member_council_points():
    ballots = [Ballot(voter="A", ranking=["B"]), Ballot(voter="B", ranking=["A"])]
    tally = tally_votes(
        ballots,
        member_order=["A", "B"],
        member_weights={"A": 1.0, "B": 1.0},
        final_answers={"A": "identical answer text", "B": "identical answer text"},
    )
    # n=2 -> top rank earns n-2 = 0 points; the tie is broken by consensus.
    assert tally.points == {"A": 0.0, "B": 0.0}
    assert tally.winner in {"A", "B"}
    assert tally.tie_broken is True


def test_uncounted_ballots_are_ignored():
    ballots = [Ballot(voter="A", ranking=[], counted=False, note="junk")]
    tally = tally_votes(
        ballots,
        member_order=["A", "B"],
        member_weights={"A": 1.0, "B": 1.0},
    )
    assert tally.winner is None
    assert tally.ignored_ballots == 1


def test_tie_broken_by_consensus_with_others():
    finals = {
        "A": "alpha beta gamma",
        "B": "alpha beta delta",
        "C": "alpha beta epsilon",
    }
    ballots = [
        Ballot(voter="A", ranking=["B", "C"]),
        Ballot(voter="B", ranking=["A", "C"]),
    ]
    # A and B tied on points; A is alphabetically first and similarity is
    # symmetric-ish, so the tie-break must still produce a deterministic
    # winner from member_order.
    tally = tally_votes(
        ballots,
        member_order=["A", "B", "C"],
        member_weights={"A": 1.0, "B": 1.0, "C": 0.0},
        final_answers=finals,
        tie_break_by_consensus=True,
    )
    assert tally.winner in {"A", "B"}
