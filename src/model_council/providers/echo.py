"""Deterministic offline provider used for demos, tests and onboarding.

``EchoProvider`` ships four personas (``optimist``, ``skeptic``,
``pragmatist``, ``generalist``) that genuinely disagree with one another:
they take different stances, cross-critique along different axes and cast
different ballots - all derived deterministically from the question text.

This makes every part of the deliberation protocol runnable with **zero API
keys**, which is essential for reproducible tests, CI and first-run demos.
It is a test double, not a model: never present its output as model output.
"""

from __future__ import annotations

import hashlib
import re

from model_council.providers.base import CompletionRequest, ModelProvider

_VOTE_BLOCK_RE = re.compile(
    r"\[Member ([A-Z])\]\s*\n(.+?)(?=\n\n\[Member [A-Z]\]|\Z)", re.S
)

_KEYWORDS = {
    "optimist": ("opportunity", "upside", "move forward", "instrument"),
    "skeptic": ("risk", "do not proceed", "validated", "underestimat"),
    "pragmatist": ("reversible", "staged", "slice", "checkpoint"),
    "generalist": ("constraint", "depends", "specify"),
}

_PERSONAS = {
    "optimist": {
        "stance": "the opportunity clearly outweighs the risk",
        "lens": "upside-first reasoning",
        "signature": "Move forward, but instrument everything so we can stop "
        "early if the signals turn negative.",
    },
    "skeptic": {
        "stance": "the risks are being systematically underestimated",
        "lens": "failure-mode reasoning",
        "signature": "Do not proceed until the two weakest assumptions are "
        "independently validated.",
    },
    "pragmatist": {
        "stance": "a staged, reversible path beats both haste and paralysis",
        "lens": "cost-of-reversibility reasoning",
        "signature": "Ship the smallest reversible slice and review the "
        "decision at a fixed checkpoint.",
    },
    "generalist": {
        "stance": "the answer depends on constraints the question does not "
        "fully specify",
        "lens": "decision-theoretic reasoning",
        "signature": "Specify the binding constraint first; the ranking of "
        "options usually falls out of it.",
    },
}

_CONFIDENCE_BASE = {"optimist": 8, "skeptic": 6, "pragmatist": 7, "generalist": 7}


def _seed(*parts: str) -> int:
    digest = hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _pick(items: list[str], seed: int) -> str:
    return items[seed % len(items)]


class EchoProvider(ModelProvider):
    """Fully deterministic, offline provider with distinct personas."""

    name = "echo"
    label = "Echo (deterministic offline test double)"
    env_var = None
    default_model = "generalist"
    offline = True

    # ------------------------------------------------------------------ util
    def _persona(self) -> str:
        return self.model if self.model in _PERSONAS else "generalist"

    # ------------------------------------------------------------- position
    def _position(self, question: str) -> str:
        p = _PERSONAS[self._persona()]
        seed = _seed(self._persona(), question)
        focus = _pick(
            [
                "long-term maintainability",
                "user trust",
                "operational cost",
                "time-to-value",
            ],
            seed,
        )
        confidence = _CONFIDENCE_BASE[self._persona()] + (seed % 2)
        return (
            f"My independent position is that {p['stance']}.\n\n"
            f"Reasoning through the lens of {p['lens']}, the decision turns "
            f"primarily on {focus}. Three supporting points:\n"
            f"1. The main uncertainty is {focus}; it should be measured, not "
            f"assumed.\n"
            f"2. Reversibility matters more than optimality under "
            f"uncertainty.\n"
            f"3. Evidence gathered after a small commitment beats debate "
            f"gathered before it.\n\n"
            f"Caveat: if {focus} degrades, this position weakens.\n\n"
            f"Confidence: {confidence}/10"
        )

    # ------------------------------------------------------------- critique
    def _critique(self, user_prompt: str) -> str:
        """Produce one structured ``[Member X]`` section per target."""
        p = _PERSONAS[self._persona()]
        letters = [letter for letter, _ in _VOTE_BLOCK_RE.findall(user_prompt)]
        sections: list[str] = []
        for letter in letters:
            seed = _seed(self._persona(), letter)
            weakness = _pick(
                [
                    "conflates correlation with causation",
                    "assumes away tail risk",
                    "optimises a metric that may not be the real objective",
                    "underweights second-order effects",
                ],
                seed,
            )
            sections.append(
                f"[Member {letter}]\n"
                "Strengths: the answer is internally coherent and states "
                "its assumptions.\n"
                f"Weaknesses: it {weakness}; the confidence level is not "
                "justified by cited evidence.\n"
                "Factual or logical risks: any quantitative claim needs an "
                "independent source before acting on it.\n"
                "Missing considerations: a rollback plan and a definition "
                "of what evidence would change the verdict."
            )
        body = "\n\n".join(sections)
        return (
            f"{body}\n\n"
            f"KEY DISAGREEMENTS:\n- whether {p['lens']} or direct empirical "
            "validation should drive the decision\n- how much tail risk is "
            "acceptable to carry"
        )

    # --------------------------------------------------------------- revise
    def _revise(self, original: str) -> str:
        p = _PERSONAS[self._persona()]
        kept = original.splitlines()[0]
        return (
            f"{kept}\n\n"
            "Revision: I keep the core position after cross-examination, "
            "but I soften the strongest claim, add the requested rollback "
            "plan, and lower stated confidence where evidence is thin.\n"
            f"{p['signature']}\n\n"
            "Confidence: 7/10"
        )

    # ----------------------------------------------------------------- vote
    def _vote(self, user_prompt: str) -> str:
        """Rank the other members' blocks by persona-keyword affinity.

        The vote prompt (like for a real model) contains only pseudonymised
        blocks ``[Member X]``. The persona scores each block for its own
        keyword bias, producing deterministic but genuinely different
        ballots per persona.
        """
        persona = self._persona()
        seed = _seed(persona, user_prompt[:300])
        blocks = _VOTE_BLOCK_RE.findall(user_prompt)
        scored = []
        for letter, body in blocks:
            lowered = body.lower()
            score = sum(lowered.count(k) for k in _KEYWORDS[persona])
            scored.append((-score, (seed + ord(letter)) % 7, letter))
        scored.sort()
        letters = [letter for _, _, letter in scored]
        ranked = letters or [name for name in _PERSONAS if name != persona]
        return (
            "BALLOT: " + ", ".join(ranked) + "\n"
            f"RATIONALE: consistent with {persona} weighting of evidence "
            "versus reversibility."
        )

    # ------------------------------------------------------------- complete
    def complete(self, request: CompletionRequest) -> str:
        prompt = request.user
        if request.task.value == "POSITION":
            return self._position(_extract_question(prompt))
        if request.task.value == "CRITIQUE":
            return self._critique(prompt)
        if request.task.value == "REVISE":
            return self._revise(_section(prompt, "YOUR ORIGINAL ANSWER"))
        if request.task.value == "VOTE":
            return self._vote(prompt)
        raise ValueError(f"Unknown task: {request.task}")  # pragma: no cover


def _extract_question(prompt: str) -> str:
    """Pull the question body out of a POSITION prompt."""
    marker = "QUESTION:"
    if marker in prompt:
        after = prompt.split(marker, 1)[1]
        return after.split("Respond with", 1)[0].strip()
    return prompt.strip()


def _section(prompt: str, header: str) -> str:
    """Extract the text block that follows ``header`` until a blank line."""
    if header not in prompt:
        return prompt.strip()
    block = prompt.split(header, 1)[1]
    lines: list[str] = []
    for line in block.splitlines()[1:]:
        if not line.strip() and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip() or prompt.strip()
