"""REST API tests via FastAPI's TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from model_council import __version__
from model_council.api.app import create_app
from model_council.api.store import DeliberationStore


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_providers_endpoint(client):
    response = client.get("/v1/providers")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["providers"]}
    assert {"echo", "openai", "anthropic", "google", "openrouter", "ollama"} <= names


def test_create_and_fetch_deliberation(client):
    created = client.post(
        "/v1/deliberations",
        json={"question": "Should the team adopt a weekly council review?"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "completed"
    assert payload["winner"]
    assert payload["rounds_completed"] == 1

    council_id = payload["council_id"]
    fetched = client.get(f"/v1/deliberations/{council_id}")
    assert fetched.status_code == 200
    assert fetched.json()["council_id"] == council_id


def test_list_deliberations(client):
    client.post("/v1/deliberations", json={"question": "First council question?"})
    listing = client.get("/v1/deliberations")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    assert body["deliberations"][0]["question"]


def test_transcript_markdown(client):
    created = client.post(
        "/v1/deliberations",
        json={"question": "Adopt contract testing before launch?"},
    ).json()
    response = client.get(
        f"/v1/deliberations/{created['council_id']}/transcript.md"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("# MODEL-COUNCIL Deliberation Transcript")


def test_unknown_deliberation_returns_404(client):
    assert client.get("/v1/deliberations/does-not-exist").status_code == 404
    assert (
        client.get("/v1/deliberations/does-not-exist/transcript.md").status_code
        == 404
    )


def test_unknown_provider_returns_400(client):
    response = client.post(
        "/v1/deliberations",
        json={"question": "Valid question?", "members": ["nosuch:model"]},
    )
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


def test_validation_errors_return_422(client):
    assert (
        client.post("/v1/deliberations", json={"question": "hi"}).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/deliberations",
            json={"question": "Valid question?", "rounds": 99},
        ).status_code
        == 422
    )


def test_store_capacity_eviction():
    store = DeliberationStore(capacity=2)
    from model_council.engine.results import DeliberationResult

    for index in range(4):
        store.save(
            DeliberationResult(question=f"question {index}", council_id=str(index))
        )
    assert len(store) == 2
    assert store.get("0") is None
    assert store.get("3") is not None
