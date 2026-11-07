# MODEL-COUNCIL

**Structured multi-model deliberation - independent positions, pseudonymised cross-critique, weighted voting, auditable transcripts.**

MODEL-COUNCIL routes one question through a council of independent AI models and returns something far more useful than a single chat completion: a fully auditable deliberation record with preserved original answers, structured disagreement analysis, explicit uncertainty, and a transparent, weighted verdict.

[![CI](https://github.com/tibatechapp-ship-it/model-council/actions/workflows/ci.yml/badge.svg)](https://github.com/tibatechapp-ship-it/model-council/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Version](https://img.shields.io/badge/version-20.0.0-blueviolet)

---

## Why MODEL-COUNCIL

A single model answer is a claim. A council answer is *evidence about claims*:

| Single-model call | MODEL-COUNCIL deliberation |
| --- | --- |
| One answer, no alternatives | Independent positions from every member |
| No cross-examination | Pseudonymised critique rounds |
| Hidden disagreement | Structured disagreement axes with attribution |
| Unstated uncertainty | Explicit per-member confidence + uncertainty report |
| No accountability trail | Verbatim transcript, exportable to Markdown/JSON |
| Vendor lock-in | Provider-neutral: 6 providers, one spec format |

**Design axiom:** model agreement must never be treated as proof of correctness. Consensus is reported as a *lexical similarity score*, never as truth.

## What's new in v20.0.0

The 0.1.0 foundation (Pydantic domain models + CLI skeleton) is now a complete deliberation framework:

- **Four-phase deliberation protocol** - POSITION -> CRITIQUE -> REVISE -> VOTE, with 0-5 configurable rounds.
- **Pseudonymised cross-critique** - members review `[Member A/B/C]`, never brand names, so popularity cannot bias review.
- **Weighted Borda voting** - self-votes impossible, partial ballots handled, ties broken by consensus with the council, everything visible in the result.
- **Structured disagreement analysis** - token-Jaccard similarity matrix, clustering, per-pair severity, member-reported axes.
- **Six providers** - OpenAI, Anthropic, Google Gemini, OpenRouter, Ollama (local), plus the deterministic offline Echo council (no API keys needed, ever).
- **REST API** - FastAPI service with OpenAPI docs, bounded in-memory store, Markdown transcript endpoint.
- **Full CLI** - `providers`, `ask`, `deliberate`, `demo`, `serve` with JSON mode and transcript export.
- **69 tests, ruff-clean, CI across Python 3.10-3.13.**

See [CHANGELOG.md](CHANGELOG.md) for the full release notes.

## Quick start (no API keys required)

```bash
python -m pip install -e ".[dev]"

# The offline demo council - Optimist, Skeptic, Pragmatist personas
model-council demo
```

That's a real, full deliberation: positions, critique round, revisions, vote, disagreement analysis - computed locally in milliseconds by deterministic test-double personas. It exists so you can learn the protocol, run CI, and validate integrations **without spending a token or leaking a secret**.

## Quick start (real providers)

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...          # or OPENROUTER_API_KEY=...
# Ollama needs no key: start `ollama serve` locally

model-council deliberate "Should we migrate the billing service to event sourcing?" \
    --members "openai:gpt-4o-mini,anthropic:claude-3-5-haiku-latest,google:gemini-2.0-flash" \
    --rounds 2 \
    --export transcript.md
```

Exit codes: `0` completed, `3` partial (some members failed - errors are recorded, deliberation continued), `4` failed, `2` usage error.

## Python API

```python
from model_council import Council, DeliberationConfig

council = Council.from_specs(
    [
        "openai:gpt-4o-mini",
        "anthropic:claude-3-5-haiku-latest",
        "ollama:llama3.1",        # local model, no key
    ],
    config=DeliberationConfig(rounds=2),
)
result = council.deliberate("Is client-side encryption sufficient for our threat model?")

print(result.winner)              # weighted-Borda winner
print(result.consensus_score)     # lexical similarity in [0, 1]
for item in result.disagreements: # structured disagreement axes
    print(item.axis, item.severity, item.groups)

result.transcript.render_markdown(result.question)  # full audit log
```

Full reference: [docs/CLI.md](docs/CLI.md), [docs/API.md](docs/API.md), [docs/PROTOCOL.md](docs/PROTOCOL.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PROVIDERS.md](docs/PROVIDERS.md).

## The protocol in one table

| Phase | What happens | Guarantees |
| --- | --- | --- |
| **POSITION** | Every member answers independently | No member sees another member's output |
| **CRITIQUE** | Each member reviews the others' answers | Pseudonyms only; per-answer sections; explicit disagreement axes |
| **REVISE** | Each member revises under received critiques | Originals are preserved verbatim, never overwritten |
| **VOTE** | Each member ranks the others' final answers | Self-votes structurally impossible; weighted Borda tally |

Failure semantics: a member that errors in any phase is recorded (phase, message) and excluded from later phases; the session continues and reports `partial`. All members failing reports `failed`. Ignored ballots are kept with a reason.

## REST API

```bash
model-council serve --host 0.0.0.0 --port 8000
```

```bash
curl -s localhost:8000/health
curl -s localhost:8000/v1/providers
curl -s -X POST localhost:8000/v1/deliberations \
     -H 'content-type: application/json' \
     -d '{"question": "Should we adopt weekly council reviews?", "rounds": 1}'
curl -s localhost:8000/v1/deliberations/<id>/transcript.md -o transcript.md
```

Interactive OpenAPI docs ship at `/docs`. Credentials are read from the **server environment only** - never from request bodies, never echoed in responses.

## Security and responsible use

- **Credentials**: providers read keys from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`). Keys are never logged, never stored in results, never sent anywhere except the provider endpoint.
- **Model output is untrusted data.** Transcripts and answers are reproduced verbatim for audit, not executed. MODEL-COUNCIL never runs model-generated commands.
- **No hidden consensus**: agreement is reported as a lexical similarity heuristic and labelled as such. The `EchoProvider` is a deterministic test double - never present its output as real model output.
- **Data retention**: the API store is bounded and process-local by design; there is no database by default.
- Read the full [Security Policy](SECURITY.md) and [docs/PROTOCOL.md](docs/PROTOCOL.md) for threat-model notes.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q          # 69 tests, fully offline
ruff check .                 # lint (E, F, I, B, UP)
```

CI runs the suite on Python 3.10/3.11/3.12/3.13 plus a Ruff job - see [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Project layout

```
src/model_council/
├── domain/       # legacy v0.1 Pydantic models (kept for compatibility)
├── providers/    # base + registry + 6 providers (+ deterministic echo)
├── engine/       # config, protocol, voting, disagreement, transcripts, Council facade
├── api/          # FastAPI app, schemas, bounded in-memory store
└── cli/          # argparse CLI + terminal rendering
tests/            # 69 offline tests across all layers
docs/             # architecture, protocol, providers, API, CLI references
examples/         # runnable scripts
```

## Research and collaboration

We welcome contributions from AI researchers, software engineers, academic institutions, independent laboratories, and open-source communities.

- [Contributing](CONTRIBUTING.md)
- [Research notes](docs/RESEARCH.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Support](SUPPORT.md)
- [Official announcement](ANNOUNCEMENT.md)

## Citation

If MODEL-COUNCIL supports your research or engineering work, cite it via [CITATION.cff](CITATION.cff) (`v20.0.0`).

## License

MIT - see [LICENSE](LICENSE).
