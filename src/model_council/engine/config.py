"""Deliberation configuration with strict bounds.

Defaults are tuned for a fast, auditable session: one critique/revision
round, four parallel workers, 60s provider timeout. Everything is a Pydantic
model so invalid CLI/API input fails early with a clear message.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeliberationConfig(BaseModel):
    """Knobs of the four-phase deliberation protocol."""

    #: Number of critique -> revision rounds (0 = single-shot positions).
    rounds: int = Field(default=1, ge=0, le=5)
    #: Parallel provider calls per phase.
    max_workers: int = Field(default=4, ge=1, le=16)
    #: Per-call provider timeout in seconds.
    timeout: float = Field(default=60.0, gt=0, le=600)
    #: Sampling temperature handed to providers.
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    #: Per-call token budget handed to providers.
    max_tokens: int = Field(default=2048, gt=0, le=32768)
    #: Jaccard similarity above which two answers count as one cluster.
    cluster_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    #: Keep original answers alongside revisions (transparency default).
    preserve_originals: bool = True
    #: Break vote ties by similarity to the rest of the council.
    tie_break_by_consensus: bool = True
