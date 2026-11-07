# CLI Reference (v20.0.0)

Entry points: `model-council` (console script) or
`python -m model_council.cli.main`.

## Global

```
model-council --version        # MODEL-COUNCIL 20.0.0
model-council --help
```

## `providers`

List every registered provider with availability and the environment
variable it needs.

```
$ model-council providers
PROVIDER     AVAILABLE  DEFAULT MODEL                NOTE
------------------------------------------------------------------------
anthropic    no         claude-3-5-haiku-latest      set ANTHROPIC_API_KEY
echo         yes        generalist                   offline test double
google       no         gemini-2.0-flash             set GOOGLE_API_KEY
ollama       no         llama3.1                     requires a local Ollama daemon
openai       no         gpt-4o-mini                  set OPENAI_API_KEY
openrouter   no         openai/gpt-4o-mini           set OPENROUTER_API_KEY
```

## `ask` - quick consult

Independent positions + vote, no debate rounds (`--rounds 0` semantics
unless overridden).

```
model-council ask "Should we enable SSO before the audit?" \
    --members "openai:gpt-4o-mini,echo:skeptic" --json
```

## `deliberate` - full protocol

Critique + revision rounds, then the weighted vote.

```
model-council deliberate "Migrate billing to event sourcing?" \
    --members "openai:gpt-4o-mini,anthropic:claude-3-5-haiku-latest,ollama:llama3.1" \
    --rounds 2 \
    --export transcript.md
```

## `demo` - offline, zero keys

Runs the deterministic echo council through the complete protocol.

```
model-council demo            # human-readable summary
model-council demo --json     # machine-readable full result
```

## `serve` - REST API

```
model-council serve --host 0.0.0.0 --port 8000
```

## Shared options (ask / deliberate / demo)

| Flag | Default | Description |
| --- | --- | --- |
| `--members` | echo demo council | comma-separated `provider:model` specs |
| `--rounds` | 1 | critique/revision rounds, 0-5 |
| `--timeout` | 60.0 | seconds per provider call |
| `--temperature` | 0.4 | sampling temperature |
| `--max-tokens` | 2048 | per-call token budget |
| `--workers` | 4 | parallel provider calls per phase |
| `--json` | off | print the full result as JSON to stdout |
| `--export PATH` | off | write `.md` transcript or `.json` full result |
| `--show-transcript` | off | append the verbatim transcript to stdout |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | completed |
| 3 | partial - some members failed (see MEMBER ERRORS section / `errors` in JSON) |
| 4 | failed - no member produced an answer |
| 2 | usage error (unknown provider, invalid input) |

## Examples

Write the full JSON result for downstream tooling:

```
model-council deliberate "Pick the vector DB" \
  --members "openai:gpt-4o-mini,google:gemini-2.0-flash" \
  --export result.json --json > /dev/null
```

A five-member weighted council (heavier vote for the local model):

```python
from model_council import Council, CouncilMember

council = Council([
    CouncilMember(name="GPT", provider="openai", model="gpt-4o-mini"),
    CouncilMember(name="Claude", provider="anthropic",
                  model="claude-3-5-haiku-latest"),
    CouncilMember(name="Local", provider="ollama", model="llama3.1",
                  weight=2.0),
])
```
