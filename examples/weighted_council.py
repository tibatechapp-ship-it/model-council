"""Build a custom, weighted council mixing real and local providers.

Run:  python examples/weighted_council.py
Requires at least one configured provider; weights tilt the vote.
"""

from model_council import Council, CouncilMember, DeliberationConfig

# Weight 2.0 = this member's ballot carries double points in the tally.
council = Council(
    members=[
        CouncilMember(
            name="Cloud fast",
            provider="openai",
            model="gpt-4o-mini",
        ),
        CouncilMember(
            name="Local guardrail",
            provider="ollama",
            model="llama3.1",
            weight=2.0,
        ),
        CouncilMember(
            name="House skeptic",
            provider="echo",
            model="skeptic",
            system_prompt=(
                "You are the designated skeptic. Challenge every "
                "unsupported claim and demand evidence. End with "
                "'Confidence: X/10'."
            ),
        ),
    ],
    config=DeliberationConfig(rounds=2, timeout=90.0),
)

result = council.deliberate(
    "Should we replace our cron jobs with a workflow engine this quarter?"
)

print(f"Winner: {result.winner}")
print(f"Tally : {result.tally.weighted_points}")
print(f"Tie broken by consensus: {result.tally.tie_broken}")
for error in result.errors:
    print(f"Member error: {error.member} [{error.phase.value}] {error.error}")
