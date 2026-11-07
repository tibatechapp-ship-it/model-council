# Architecture

MODEL-COUNCIL is a layered, dependency-light Python package. Data flows
strictly downward: the CLI/API adapt user input, the engine orchestrates
the protocol, providers speak to models. No layer reaches upward.

```
┌────────────────────────────────────────────────────────────┐
│  cli/main.py          api/app.py (FastAPI)                 │   interface layer
│      │                     │                               │
│      ▼                     ▼                               │
│  engine/council.py  -  Council facade                      │   orchestration
│      │   members, config, registry resolution              │
│      ▼                                                     │
│  engine/protocol.py -  ProtocolRunner (4 phases)           │
│      │   prompts ▸ calls ▸ parses ▸ transcript             │
│      ├── engine/voting.py        weighted Borda tally      │
│      ├── engine/disagreement.py  similarity + clustering   │
│      ├── engine/transcript.py    append-only audit log     │
│      └── engine/results.py       DeliberationResult        │
│      ▼                                                     │
│  providers/*  -  ModelProvider implementations             │   provider layer
│      echo │ openai │ anthropic │ google │ openrouter │ ollama│
└────────────────────────────────────────────────────────────┘
```

## Components

### `engine/council.py` - the facade

`Council` owns the member list (`CouncilMember`: name, provider, model,
weight, optional custom system prompt), validates inputs, deduplicates
names, and delegates to `ProtocolRunner`. `Council.from_specs` accepts
compact `"provider:model"` strings; `Council.echo_council` builds the
offline demo council.

### `engine/protocol.py` - the orchestrator

`ProtocolRunner` resolves each member's provider from the registry,
assigns pseudonyms (`Member A`...), then executes the four phases. Every
provider call happens through `_call_providers`, which runs calls in a
thread pool (bounded by `max_workers`), preserves member order for
determinism, and converts any failure into a recorded `MemberError` that
marks the member failed for the rest of the session.

Parsing utilities (`parse_confidence`, `parse_ballot`,
`parse_critique_sections`) are pure functions over member text and are
unit-tested in isolation.

### `engine/voting.py` - weighted Borda

Rules are documented in [PROTOCOL.md](PROTOCOL.md). The tally keeps both
raw and weighted points, a tie-break flag, and every ballot - including
ignored ones with reasons - so the verdict is always reconstructible.

### `engine/disagreement.py` - lexical divergence

Pure heuristics, no model calls: tokenisation (stopword-filtered),
pairwise Jaccard similarity, union-find clustering at a configurable
threshold, and disagreement items enriched with member-reported axes.
These numbers describe *textual* divergence; they are reported as
heuristics, never as semantic truth.

### `providers/` - the boundary to models

Each provider is one HTTP shape behind the tiny `ModelProvider` ABC. The
shared `post_json` helper adds timeouts, bounded retries on 429/5xx, and
typed errors. Credentials are read from the environment once at
construction, never logged, never serialised into results. `EchoProvider`
is a deterministic test double that implements all four task behaviours
offline.

## Key design decisions

| Decision | Rationale |
| --- | --- |
| Pseudonyms in cross-member prompts | Removes brand bias from critique and voting |
| Originals preserved beside revisions | Transparency; enables before/after audits |
| Failures are data, not exceptions | Partial truth beats no truth; errors appear in the result |
| Lexical similarity, clearly labelled | Deterministic, explainable, honest about limits |
| Bounded in-memory store | Zero default data-retention surface |
| Sync providers + thread pool | Simple, robust; matches request/response model |
| Deterministic echo personas | Reproducible tests and CI without secrets |

## Threading model

Provider calls within a phase run in a `ThreadPoolExecutor`
(`DeliberationConfig.max_workers`, default 4). Phases are sequential
barriers: critique needs all positions, revision needs all critiques,
voting needs all revisions. The API runs each deliberation in FastAPI's
threadpool; the store is `threading.Lock`-protected.

## Extension points

- **Add a provider**: implement `ModelProvider.complete`, add one line to
  the registry map. It is immediately usable in every interface.
- **Change the protocol**: phases live in `ProtocolRunner`; each phase is
  a private method with a single responsibility.
- **Alternative aggregation**: `tally_votes` is a pure function; swap it
  for approval voting or Condorcet without touching the protocol.
