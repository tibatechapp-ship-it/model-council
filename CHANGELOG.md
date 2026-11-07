# Changelog

All notable changes to MODEL-COUNCIL are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project versions with [SemVer](https://semver.org/).

## [20.0.0] - 2026-11-07

The foundational 0.1.0 skeleton becomes a complete, tested, documented
multi-model deliberation framework. Everything below is implemented and
covered by the offline test suite (69 tests).

### Added - Deliberation engine (`model_council.engine`)

- Four-phase deliberation protocol: **POSITION -> CRITIQUE -> REVISE ->
  VOTE**, with 0-5 configurable critique/revision rounds
  (`DeliberationConfig`).
- Structural anonymisation: critique and vote prompts contain pseudonyms
  (`Member A`, `Member B`, ...) only - provider brands never reach
  cross-review prompts.
- **Weighted Borda voting** with self-vote exclusion, partial-ballot
  handling, per-voter weights, consensus-based tie-breaking, and retained
  ignored ballots (with reasons).
- **Structured disagreement analysis**: token-Jaccard similarity matrix,
  union-find clustering of answers, per-pair severity scores, and
  member-reported critique axes attached as sources.
- Lexical **shared-themes** extraction and **uncertainty reporting**
  (low-confidence members, explicit caveats).
- Append-only, verbatim **Transcript** with Markdown rendering for audits;
  originals are preserved even after revision.
- Graceful degradation: member failures are recorded per phase and the
  session continues (`partial` status); total failure reports `failed`;
  deterministic, documented exit codes.
- Legacy adapter: `DeliberationResult.to_council_result()` keeps the
  v0.1 `domain.CouncilResult` shape working.

### Added - Providers (`model_council.providers`)

- Provider abstraction (`ModelProvider`, `CompletionRequest`, task kinds)
  and a declarative registry with eager member-spec validation
  (`provider:model` specs).
- **OpenAI** (Chat Completions, `OPENAI_API_KEY`), **Anthropic** (Messages
  API, `ANTHROPIC_API_KEY`), **Google Gemini** (`GOOGLE_API_KEY`),
  **OpenRouter** (`OPENROUTER_API_KEY`), **Ollama** (local daemon, no key).
- Shared HTTP layer: bounded retries on 429/5xx, timeouts, typed errors,
  truncated untrusted error bodies, no credential logging.
- **EchoProvider**: deterministic offline personas (`optimist`, `skeptic`,
  `pragmatist`, `generalist`) that take distinct stances, cross-critique,
  and cast different ballots - full protocol runs with zero API keys for
  demos, tests and CI.

### Added - CLI (`model_council.cli`)

- Commands: `providers`, `ask` (positions + vote), `deliberate` (full
  protocol), `demo` (offline), `serve` (REST API).
- `--members` compact specs, `--rounds`, `--json`, `--export`
  (Markdown/JSON), `--show-transcript`, per-call tuning flags.
- Documented exit codes: 0 completed / 3 partial / 4 failed / 2 usage.

### Added - REST API (`model_council.api`)

- FastAPI service: `GET /health`, `GET /v1/providers`,
  `POST /v1/deliberations`, `GET /v1/deliberations`,
  `GET /v1/deliberations/{id}`,
  `GET /v1/deliberations/{id}/transcript.md`.
- Bounded, thread-safe, process-local store (default capacity 128) - no
  database, no credential storage.
- Validation-driven errors: 400 unknown provider, 422 invalid body,
  404 unknown deliberation.

### Changed

- `pyproject.toml` version bumped to 20.0.0; `httpx` added as a runtime
  dependency; package description updated.
- `CITATION.cff` updated to v20.0.0 with keywords and release date.
- README rewritten around the deliberation protocol and quick starts.

### Compatibility

- The v0.1 domain models (`CouncilMode`, `CouncilRequest`,
  `CouncilResult`, ...) and their tests are unchanged and still pass.

## [0.1.0] - Initial foundation

- Python package structure, Pydantic domain models, CLI skeleton
  (`--version`), first domain-model tests, CI workflow, and community
  documentation (SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, RESEARCH).
