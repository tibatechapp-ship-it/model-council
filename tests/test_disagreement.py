"""Tests for lexical disagreement analysis."""

from __future__ import annotations

from model_council.engine.disagreement import (
    analyze_disagreements,
    cluster_members,
    common_themes,
    jaccard,
    tokenize,
)


def test_tokenize_removes_stopwords():
    tokens = tokenize("The council will review the evidence")
    assert "council" in tokens
    assert "the" not in tokens
    assert "will" not in tokens


def test_jaccard_bounds():
    assert jaccard("alpha beta", "alpha beta") == 1.0
    assert jaccard("alpha beta", "gamma delta") == 0.0
    assert jaccard("", "alpha") == 0.0


def test_cluster_members_groups_similar_answers():
    answers = {
        "A": "ship the release on friday after review",
        "B": "ship the release on friday after peer review",
        "C": "delay everything for six months",
    }
    clusters = cluster_members(answers, threshold=0.5)
    assert len(clusters) == 2
    flat = [name for group in clusters for name in group]
    assert flat == ["A", "B", "C"]


def test_analyze_disagreements_sorted_by_severity():
    answers = {
        "A": "ship the release on friday after review",
        "B": "delay everything for six months",
        "C": "postpone the release indefinitely",
    }
    items = analyze_disagreements(answers, cluster_threshold=0.5)
    assert items, "expected at least one disagreement item"
    severities = [item.severity for item in items]
    assert severities == sorted(severities, reverse=True)
    for item in items:
        assert len(item.groups) == 2
        assert 0.0 <= item.similarity <= 1.0


def test_reported_axes_enrich_sources():
    answers = {"A": "ship now", "B": "delay now"}
    axes = [("A", "B", "timing of the release")]
    items = analyze_disagreements(answers, reported_axes=axes)
    assert items[0].sources
    assert "timing of the release" in items[0].axis


def test_common_themes_majority_tokens():
    answers = {
        "A": "the rollout needs a rollback plan",
        "B": "a rollback plan is essential for rollout",
        "C": "sunspots are unrelated here",
    }
    themes = common_themes(answers)
    assert "rollback" in themes.themes
    assert "sunspots" not in themes.themes
