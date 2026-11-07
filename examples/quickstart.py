"""Quickstart: a full offline deliberation in ~15 lines.

Run:  python examples/quickstart.py
No API keys required - the echo council is a deterministic test double.
"""

from model_council import Council

council = Council.echo_council()  # Optimist, Skeptic, Pragmatist
result = council.deliberate(
    "Should a small team adopt a weekly model-council review for "
    "high-stakes architectural decisions?"
)

print(f"Status      : {result.status.value}")
print(f"Winner      : {result.winner} (weighted Borda)")
print(f"Consensus   : {result.consensus_score:.2f} (lexical heuristic)")
print(f"Rounds      : {result.rounds_completed}/{result.rounds_requested}")
print("\nDisagreement axes:")
for item in result.disagreements:
    groups = " vs ".join("/".join(g) for g in item.groups)
    print(f"  - {item.axis} [{groups}] severity={item.severity:.2f}")

print("\nFull audit transcript:")
print(result.transcript.render_markdown(result.question))
