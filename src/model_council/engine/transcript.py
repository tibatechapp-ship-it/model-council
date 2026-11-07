"""Structured, exportable deliberation transcripts.

Every phase, every member statement and every failure is appended to a
:class:`Transcript`. Transcripts render to Markdown (human audit) or JSON
(machine processing) and are preserved verbatim - the engine never rewrites
what a member said, it only annotates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Phase(str, Enum):
    POSITION = "position"
    CRITIQUE = "critique"
    REVISE = "revise"
    VOTE = "vote"


class Event(BaseModel):
    """One statement or system note inside a deliberation."""

    phase: Phase
    round_number: int = Field(default=0, ge=0)
    actor: str
    pseudonym: str | None = None
    content: str
    meta: dict[str, str] = Field(default_factory=dict)


class Transcript(BaseModel):
    """Ordered, append-only log of a deliberation."""

    events: list[Event] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add(
        self,
        phase: Phase,
        actor: str,
        content: str,
        *,
        round_number: int = 0,
        pseudonym: str | None = None,
        **meta: str,
    ) -> Event:
        event = Event(
            phase=phase,
            round_number=round_number,
            actor=actor,
            pseudonym=pseudonym,
            content=content,
            meta=dict(meta),
        )
        self.events.append(event)
        return event

    def add_system_note(self, note: str) -> Event:
        return self.add(Phase.POSITION, actor="council", content=note)

    def render_markdown(self, question: str) -> str:
        """Render the full deliberation as an audit-ready Markdown report."""
        lines: list[str] = [
            "# MODEL-COUNCIL Deliberation Transcript",
            "",
            f"- **Generated:** {self.created_at.isoformat(timespec='seconds')}",
            f"- **Question:** {question}",
            "",
            "> Transcripts are verbatim records. Statements are reproduced "
            "exactly as received from each member; nothing below is "
            "paraphrased or repaired by the engine.",
            "",
        ]
        current_phase: tuple[Phase, int] | None = None
        for event in self.events:
            key = (event.phase, event.round_number)
            if key != current_phase:
                current_phase = key
                label = event.phase.value.upper()
                round_part = (
                    f" - Round {event.round_number}"
                    if event.round_number
                    else ""
                )
                lines.append(f"## Phase: {label}{round_part}")
                lines.append("")
            who = event.actor
            if event.pseudonym:
                who = f"{event.actor} (`{event.pseudonym}`)"
            if event.actor == "council":
                lines.append(f"*{event.content}*")
                lines.append("")
                continue
            lines.append(f"### {who}")
            lines.append("")
            lines.append(event.content.rstrip())
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
