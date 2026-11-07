# REST API Reference (v20.0.0)

Run the server:

```bash
model-council serve --host 127.0.0.1 --port 8000
# or: uvicorn model_council.api.app:app --port 8000
```

Interactive OpenAPI documentation ships at `/docs`; the raw schema at
`/openapi.json`.

## System

### `GET /health`

```json
{"status": "ok", "version": "20.0.0"}
```

### `GET /v1/providers`

Provider introspection:

```json
{
  "providers": [
    {"name": "openai", "label": "OpenAI (Chat Completions)",
     "env_var": "OPENAI_API_KEY", "default_model": "gpt-4o-mini",
     "offline": false, "available": false}
  ]
}
```

## Deliberations

### `POST /v1/deliberations` -> 201

Request body:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `question` | string | required | 3..20000 chars |
| `members` | list[string] | echo demo council | specs `provider:model` |
| `rounds` | int | 1 | 0..5 |
| `timeout` | float | 60.0 | seconds per provider call |
| `temperature` | float | 0.4 | 0..2 |
| `max_tokens` | int | 2048 | per call |
| `metadata` | object | `{}` | free-form string map (stored, unused) |

```bash
curl -s -X POST localhost:8000/v1/deliberations \
  -H 'content-type: application/json' \
  -d '{"question":"Should we adopt weekly council reviews?",
       "members":["openai:gpt-4o-mini","anthropic:claude-3-5-haiku-latest"],
       "rounds":2}'
```

The response is the **full `DeliberationResult`** (same shape as the
Python API): `status`, `members`, `positions`, `critiques`, `revisions`,
`ballots`, `tally`, `winner`, `consensus_score`, `agreements`,
`disagreements`, `uncertainties`, `errors`, `duration_ms`, `transcript`,
`council_id`.

Check the `status` field for the outcome: `completed`, `partial` (some
members failed - see `errors`), or `failed`.

Errors: `400` unknown provider, `422` invalid body (validation).

### `GET /v1/deliberations`

```json
{"deliberations": [{"council_id": "...", "question": "...",
                    "status": "completed", "winner": "Optimist",
                    "consensus_score": 0.41, "created_at": "..."}],
 "count": 1}
```

### `GET /v1/deliberations/{council_id}` -> 200 | 404

The stored `DeliberationResult`.

### `GET /v1/deliberations/{council_id}/transcript.md`

The verbatim Markdown transcript (`text/plain`), starting with
`# MODEL-COUNCIL Deliberation Transcript`.

## Data handling

- Results live in a bounded, thread-safe, **process-local** store
  (capacity 128, FIFO eviction). Restarting the server clears it.
- There is no database, no external persistence, no credential storage.
- Provider credentials are read from the server environment only and are
  never echoed in any response.
