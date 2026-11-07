"""Lexical disagreement analysis.

The engine never asks a model "do you agree?" and trusts the answer.
Instead it measures divergence directly:

* pairwise token-Jaccard similarity between final answers,
* greedy union-find clustering at a configurable threshold,
* one :class:`DisagreementItem` per pair of clusters that falls below the
  threshold, enriched with member-reported critique axes when available.

All heuristics are lexical, deterministic and documented - agreement is
never treated as proof of correctness.
"""

from __future__ import annotations

import re
from re import Pattern

from pydantic import BaseModel, Field

_TOKEN_RE: Pattern[str] = re.compile(r"[a-z0-9]{3,}")

STOPWORDS: frozenset[str] = frozenset(
    """
    the and that this with from have has was were are our their its this
    these those for not but all any can will would should could into about
    over under more most less least than then when where what which while
    who whom why how your you our out only same other another because
    answer answers member members question point points claim claims
    evidence confidence rationale strengths weaknesses risks missing
    """.split()
)


def tokenize(text: str) -> set[str]:
    """Lower-cased content words of ``text`` (stopwords removed)."""
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in STOPWORDS
    }


def jaccard(a: str, b: str) -> float:
    """Token Jaccard similarity in ``[0, 1]``; empty inputs score 0."""
    tokens_a, tokens_b = tokenize(a), tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union)


def similarity_matrix(
    answers: dict[str, str],
) -> dict[tuple[str, str], float]:
    """All ordered pairwise similarities between member answers."""
    names = sorted(answers)
    matrix: dict[tuple[str, str], float] = {}
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            score = jaccard(answers[first], answers[second])
            matrix[(first, second)] = score
            matrix[(second, first)] = score
    return matrix


def cluster_members(
    answers: dict[str, str], threshold: float = 0.5
) -> list[list[str]]:
    """Union-find clustering of members by answer similarity."""
    names = sorted(answers)
    parent: dict[str, str] = {name: name for name in names}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    matrix = similarity_matrix(answers)
    for (first, second), score in matrix.items():
        if score >= threshold and first < second:
            parent[find(first)] = find(second)

    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(find(name), []).append(name)
    return sorted(
        (sorted(group) for group in groups.values()),
        key=lambda group: group[0],
    )


class DisagreementItem(BaseModel):
    """One structured axis of disagreement between final answers."""

    axis: str
    groups: list[list[str]] = Field(default_factory=list)
    similarity: float = Field(ge=0.0, le=1.0)
    severity: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class AgreementThemes(BaseModel):
    """Themes shared by the majority of final answers (heuristic)."""

    themes: list[str] = Field(default_factory=list)
    method: str = "majority token overlap (lexical heuristic)"


def common_themes(
    answers: dict[str, str], limit: int = 5
) -> AgreementThemes:
    """Tokens present in at least two thirds of the final answers."""
    if not answers:
        return AgreementThemes()
    required = max(2, (len(answers) * 2 + 2) // 3)
    counts: dict[str, int] = {}
    for text in answers.values():
        for token in tokenize(text):
            counts[token] = counts.get(token, 0) + 1
    shared = sorted(
        (token for token, count in counts.items() if count >= required),
        key=lambda token: (-counts[token], token),
    )
    return AgreementThemes(themes=shared[:limit])


def analyze_disagreements(
    answers: dict[str, str],
    *,
    cluster_threshold: float = 0.5,
    reported_axes: list[tuple[str, str, str]] | None = None,
) -> list[DisagreementItem]:
    """Build structured disagreement items.

    ``reported_axes`` carries ``(critic, target, axis_text)`` triples
    extracted from CRITIQUE phase output, used to name the axes members
    themselves flagged.
    """
    matrix = similarity_matrix(answers)
    groups = cluster_members(answers, cluster_threshold)
    items: list[DisagreementItem] = []
    reported_axes = reported_axes or []

    for i, left in enumerate(groups):
        for right in groups[i + 1:]:
            pair_scores = [
                score
                for (a, b), score in matrix.items()
                if a in left and b in right
            ]
            similarity = (
                sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
            )
            members_involved = set(left) | set(right)
            sources = [
                f"{critic} -> {target}: {axis_text}"
                for critic, target, axis_text in reported_axes
                if critic in members_involved and target in members_involved
            ]
            axis_label = sources[0].split(": ", 1)[1] if sources else (
                "lexical divergence on core claims"
            )
            items.append(
                DisagreementItem(
                    axis=axis_label,
                    groups=[left, right],
                    similarity=round(similarity, 3),
                    severity=round(1.0 - similarity, 3),
                    sources=sources,
                )
            )

    items.sort(key=lambda item: (-item.severity, item.axis))
    return items
