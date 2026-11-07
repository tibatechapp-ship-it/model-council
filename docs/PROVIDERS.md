# Providers

MODEL-COUNCIL is provider-neutral: every model enters the council through
the same `ModelProvider` interface and the same compact member-spec
format.

## Member specs

```
provider[:model]
```

| Spec | Provider | Model | Credential |
| --- | --- | --- | --- |
| `echo:optimist` | Echo (offline test double) | persona: `optimist`, `skeptic`, `pragmatist`, `generalist` | none |
| `openai:gpt-4o-mini` | OpenAI Chat Completions | any chat model | `OPENAI_API_KEY` |
| `anthropic:claude-3-5-haiku-latest` | Anthropic Messages API | any messages model | `ANTHROPIC_API_KEY` |
| `google:gemini-2.0-flash` | Google Gemini `generateContent` | any Gemini model | `GOOGLE_API_KEY` |
| `openrouter:openai/gpt-4o-mini` | OpenRouter (OpenAI-compatible) | router slug | `OPENROUTER_API_KEY` |
| `ollama:llama3.1` | Ollama local daemon | any pulled tag | none |

Omitting the model uses the provider default. Base URLs can be overridden
with `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `GOOGLE_BASE_URL`,
`OPENROUTER_BASE_URL`, `OLLAMA_BASE_URL`.

Unknown providers are rejected **eagerly** (before any network activity):
the CLI exits with code 2, the API returns HTTP 400.

## Behaviour details

- **Timeouts**: `DeliberationConfig.timeout` (default 60s) applies to
  every provider call; Ollama probes use a short 5s availability check.
- **Retries**: 429/5xx responses are retried up to 2 times with linear
  backoff. Transport errors are typed as `ProviderRequestError`;
  malformed payloads as `ProviderResponseError`.
- **Credentials**: read from the environment at provider construction.
  They are never logged, never stored in results or transcripts, and
  never sent anywhere except the provider endpoint. The API never accepts
  credentials from request bodies.
- **Error bodies** from providers are truncated before being surfaced;
  they are treated as untrusted input.

## The Echo provider (offline, deterministic)

`echo` is not a model. It is a deterministic test double with four
personas that genuinely disagree: they take different stances, critique
along different axes, revise under critique, and cast persona-biased
ballots. All output is derived from the question text by hashing, so:

- the same question always yields the same deliberation;
- the full protocol runs with **zero API keys**;
- CI never touches the network and never costs anything.

Use it for onboarding, tests, protocol experiments and CI. Never present
echo output as real model output; it is labelled `offline test double` in
`model-council providers`.

## Adding a custom provider

```python
from model_council.providers import register_provider
from model_council.providers.base import CompletionRequest, ModelProvider

class MyProvider(ModelProvider):
    name = "myprovider"
    label = "My internal gateway"
    env_var = "MYPROVIDER_API_KEY"
    default_model = "my-model"

    def complete(self, request: CompletionRequest) -> str:
        ...  # one HTTPS call, return text

register_provider(MyProvider)
```

After registration, `"myprovider:my-model"` works in the CLI, the API and
`Council.from_specs` alike. See `providers/http.py` for a ready-made
`post_json` helper with retries and typed errors.
