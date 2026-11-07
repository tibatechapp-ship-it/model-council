"""Human-readable rendering of council results for the terminal.

Pure text formatting: no third-party terminal libraries, so the CLI stays
dependency-light and behaves identically over SSH, CI logs and pipes.
"""

from __future__ import annotations

from model_council.engine.results import DeliberationResult

_WIDTH = 72


def _rule(title: str) -> str:
    return f"\n{'=' * _WIDTH}\n{title}\n{'=' * _WIDTH}"


def truncate(text: str, limit: int = 400) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " [...truncated]"


def render_providers(items: list[dict]) -> str:
    lines = [
        f"{'PROVIDER':<12} {'AVAILABLE':<10} {'DEFAULT MODEL':<28} NOTE",
        "-" * _WIDTH,
    ]
    for item in items:
        available = "yes" if item["available"] else "no"
        note = ""
        if item["offline"]:
            note = "offline test double"
        elif item["env_var"] and not item["available"]:
            note = f"set {item['env_var']}"
        elif item["name"] == "ollama":
            note = "requires a local Ollama daemon"
        lines.append(
            f"{item['name']:<12} {available:<10} {item['default_model']:<28} {note}"
        )
    return "\n".join(lines)


def render_summary(result: DeliberationResult, show_transcript: bool = False) -> str:
    parts: list[str] = []
    parts.append(_rule(f"MODEL-COUNCIL - {result.status.value.upper()}"))
    parts.append(f"Question      : {truncate(result.question, 120)}")
    parts.append(f"Members       : {', '.join(result.members)}")
    parts.append(
        f"Rounds        : {result.rounds_completed}/{result.rounds_requested}"
    )
    parts.append(f"Consensus     : {result.consensus_score:.2f} (lexical)")
    parts.append(f"Duration      : {result.duration_ms} ms")
    parts.append(f"Council ID    : {result.council_id}")

    winner = result.winner or "none (no decisive vote)"
    parts.append(_rule("COUNCIL VERDICT"))
    parts.append(f"Winner (weighted Borda): {winner}")
    weighted = "  ".join(
        f"{name}: {points:g}"
        for name, points in sorted(
            result.tally.weighted_points.items(), key=lambda kv: -kv[1]
        )
    )
    parts.append(f"Weighted points        : {weighted or 'n/a'}")
    if result.tally.tie_broken:
        parts.append("Note: tie broken by consensus with the council.")
    if result.tally.ignored_ballots:
        parts.append(
            f"Ignored ballots: {result.tally.ignored_ballots} "
            "(no parsable BALLOT block)"
        )
    for ballot in result.tally.ballots:
        vote = ", ".join(ballot.ranking) if ballot.ranking else "(none)"
        parts.append(f"  {ballot.voter} -> {vote}")

    parts.append(_rule("FINAL ANSWERS (after deliberation)"))
    finals = _finals(result)
    for name, text in finals.items():
        parts.append(f"\n--- {name} " + "-" * max(_WIDTH - len(name) - 8, 3))
        parts.append(truncate(text, 900))
        for turn in result.revisions + result.positions:
            if turn.member == name and turn.confidence is not None:
                parts.append(f"[confidence {turn.confidence:.0%}]")
                break

    if result.disagreements:
        parts.append(_rule("STRUCTURED DISAGREEMENTS"))
        for index, item in enumerate(result.disagreements, start=1):
            groups = " vs ".join("/".join(group) for group in item.groups)
            parts.append(
                f"{index}. {item.axis} "
                f"[{groups}] similarity={item.similarity:.2f}"
            )
            for source in item.sources[:3]:
                parts.append(f"   - {truncate(source, 100)}")

    if result.agreements.themes:
        parts.append(_rule("SHARED THEMES (lexical, not proof of truth)"))
        parts.append(", ".join(result.agreements.themes))

    if result.uncertainties:
        parts.append(_rule("REPORTED UNCERTAINTIES"))
        parts.extend(f"- {item}" for item in result.uncertainties)

    if result.errors:
        parts.append(_rule("MEMBER ERRORS"))
        parts.extend(
            f"- {e.member} [{e.phase.value}]: {e.error}" for e in result.errors
        )

    if show_transcript:
        parts.append(_rule("FULL TRANSCRIPT"))
        parts.append(result.transcript.render_markdown(result.question))
    else:
        parts.append(
            "\nTip: --export transcript.md writes the full verbatim audit log."
        )
    return "\n".join(parts)


def _finals(result: DeliberationResult) -> dict[str, str]:
    finals: dict[str, str] = {}
    if result.revisions:
        # latest revision per member wins
        for turn in result.revisions:
            finals[turn.member] = turn.content
    for turn in result.positions:
        finals.setdefault(turn.member, turn.content)
    return finals
