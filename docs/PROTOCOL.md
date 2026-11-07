# The Deliberation Protocol

This document specifies the MODEL-COUNCIL deliberation protocol as
implemented by `engine/protocol.py` in v20.0.0.

## Overview

One question in, one auditable deliberation out. The protocol has four
phases; critique and revision repeat for a configurable number of rounds
(0-5, default 1).

```
        ┌────────────┐
        │  POSITION  │  every member answers independently
        └─────┬──────┘
              ▼
   ┌─────────────────────┐      rounds 1..N
   │      CRITIQUE       │  pseudonymised cross-review
   └─────┬───────────────┘
         ▼
   ┌─────────────────────┐
   │       REVISE        │  members fix their own answers
   └─────┬───────────────┘
         ▼ (after N rounds)
   ┌─────────────────────┐
   │        VOTE         │  rank others' finals, weighted Borda
   └─────────────────────┘
```

## Phase 1 - POSITION

Every active member receives:

- system: its identity and independence instruction ("do not guess what
  other members might say", "state uncertainty explicitly", "end with
  `Confidence: X/10`"),
- user: `TASK: POSITION` + the verbatim question.

**Guarantee:** no member sees any other member's output. The engine runs
these calls in parallel; order is preserved by member index.

The stated `Confidence: n/10` is parsed and stored per turn
(`MemberTurn.confidence` in `[0, 1]`).

## Phase 2 - CRITIQUE (round r)

Each member receives the *latest* answer of every other member,
pseudonymised and clipped at 6000 chars each:

```
ANSWERS FROM OTHER MEMBERS (anonymised):
[Member B]
...

[Member C]
...
```

and is asked for, per answer: Strengths / Weaknesses / Factual or logical
risks / Missing considerations, followed by a `KEY DISAGREEMENTS:` block.

The engine parses `[Member X]` sections back to concrete
`(critic, target)` pairs (`CritiqueTurn`) and collects disagreement axes
as attributed `(critic, target, axis)` triples.

**Guarantee:** brand names never enter cross-review prompts. A member
cannot tell which vendor produced `Member B`'s text from the prompt
alone.

## Phase 3 - REVISE (round r)

Each member receives its own latest answer plus the critiques it
*received* (target == self, current round) and is asked to keep what
survives scrutiny, fix what was correctly criticised, and state what
remains uncertain.

**Guarantee:** originals are never overwritten. `result.positions` keeps
the first-round answers; `result.revisions` records what changed.

## Phase 4 - VOTE

Each member receives the other members' *final* answers, pseudonymised,
and must answer exactly:

```
BALLOT: <letters, best first, comma-separated>
RATIONALE: <one line>
```

Parsing rules:

- self-references and unknown letters are dropped;
- duplicates are deduplicated;
- a ballot with no parsable `BALLOT:` block is **kept but ignored**
  (`counted=False`, `note` records the reason).

### Weighted Borda tally

With `n` council members, a ballot's first-ranked member earns `n-2`
points, the next `n-3`, ... down to 0. Each voter's points are multiplied
by the voter's `weight` (default 1.0). Highest weighted total wins.

Tie-breaking (in order): (1) similarity to the rest of the council
(mean Jaccard of the leader's final answer against the others), (2)
stable member order. Both are deterministic and flagged
(`tally.tie_broken`).

**Guarantee:** self-votes are structurally impossible - the vote prompt
only contains other members' answers, and the tally rejects any
self-reference.

## Aggregation and reporting

- `consensus_score`: mean pairwise token-Jaccard similarity of final
  answers in `[0, 1]`. **This is a lexical heuristic, not proof of
  correctness.**
- `agreements.themes`: tokens present in at least two thirds of final
  answers (labelled with its method).
- `disagreements`: one `DisagreementItem` per below-threshold cluster
  pair, with severity `1 - similarity` and attributed critique axes.
- `uncertainties`: members reporting `Confidence <= 6/10` on their final
  answer, plus explicit `Caveat:`/`Uncertain...` lines.
- `transcript`: the verbatim, append-only record of everything above.

## Failure semantics

| Event | Behaviour |
| --- | --- |
| Member fails in any phase | Recorded in `result.errors` (phase + message), member excluded from later phases, session continues |
| All members fail | `status = failed`, no winner declared |
| Some members fail | `status = partial`, survivors complete the protocol |
| Fewer than 2 active members at critique time | Critique/revision skipped, vote skipped, no winner |
| Unparsable ballot | Ballot kept with `counted=False` |

## Limits (stated honestly)

- Similarity and themes are lexical: paraphrases reduce the score,
  shared vocabulary inflates it.
- Confidence numbers are self-reported by models and are not calibrated
  probabilities.
- Voting measures *convincingness among council members*, not ground
  truth. Evidence verification (fetching and checking sources) is a
  planned, separate engine stage and is deliberately not simulated here.
