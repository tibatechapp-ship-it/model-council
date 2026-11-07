"""FastAPI application exposing the deliberation engine over HTTP.

Endpoints
---------
``GET  /health``                                 liveness + version
``GET  /v1/providers``                           provider introspection
``POST /v1/deliberations``                       run a deliberation (201)
``GET  /v1/deliberations``                       list stored deliberations
``GET  /v1/deliberations/{council_id}``          fetch one deliberation
``GET  /v1/deliberations/{council_id}/transcript.md``  Markdown transcript

Notes
-----
* ``POST`` returns HTTP 201 with the full result; check the ``status``
  field (``completed`` / ``partial`` / ``failed``) for the outcome.
* Results are held in a bounded, process-local store. There is no
  database, no external persistence and no credential storage.
* Provider credentials are read from the server environment only; they are
  never accepted from request bodies and never echoed in responses.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from model_council import __version__
from model_council.api.schemas import (
    DeliberationCreateRequest,
    DeliberationListEntry,
)
from model_council.api.store import DeliberationStore
from model_council.engine import Council, DeliberationConfig
from model_council.engine.results import DeliberationResult
from model_council.providers import available_providers

_DEFAULT_MEMBERS = ["echo:optimist", "echo:skeptic", "echo:pragmatist"]

DESCRIPTION = """
Deliberation-as-a-service: route one question through an independent
council of AI models - independent positions, pseudonymised cross-critique,
revision, and a weighted vote - and receive a fully auditable result.
"""


def create_app(store: DeliberationStore | None = None) -> FastAPI:
    app = FastAPI(
        title="MODEL-COUNCIL API",
        description=DESCRIPTION,
        version=__version__,
    )
    results = store or DeliberationStore()

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/providers", tags=["system"])
    def providers() -> dict:
        return {"providers": available_providers()}

    @app.post("/v1/deliberations", status_code=201, tags=["deliberations"])
    def create_deliberation(
        request: DeliberationCreateRequest,
    ) -> DeliberationResult:
        specs = request.members or _DEFAULT_MEMBERS
        config = DeliberationConfig(
            rounds=request.rounds,
            timeout=request.timeout,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        try:
            council = Council.from_specs(specs, config=config)
            result = council.deliberate(request.question)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        results.save(result)
        return result

    @app.get("/v1/deliberations", tags=["deliberations"])
    def list_deliberations() -> dict:
        entries = [
            DeliberationListEntry(
                council_id=result.council_id,
                question=result.question,
                status=result.status,
                winner=result.winner,
                consensus_score=result.consensus_score,
                created_at=result.created_at,
            )
            for result in results.list()
        ]
        return {"deliberations": entries, "count": len(entries)}

    @app.get("/v1/deliberations/{council_id}", tags=["deliberations"])
    def get_deliberation(council_id: str) -> DeliberationResult:
        result = results.get(council_id)
        if result is None:
            raise HTTPException(
                status_code=404, detail="Deliberation not found."
            )
        return result

    @app.get(
        "/v1/deliberations/{council_id}/transcript.md",
        response_class=PlainTextResponse,
        tags=["deliberations"],
    )
    def get_transcript(council_id: str) -> str:
        result = results.get(council_id)
        if result is None:
            raise HTTPException(
                status_code=404, detail="Deliberation not found."
            )
        return result.transcript.render_markdown(result.question)

    return app


app = create_app()
