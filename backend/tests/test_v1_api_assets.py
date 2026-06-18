from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.rag.evidence_store import EvidenceStore
from app.schema.short_drama import Registry


def sample_novel_text() -> str:
    return "\n".join(
        [
            "Mira finds a sealed letter and decides to reopen the case.",
            "Rowan hides the letter in the archive before dawn.",
        ]
    )


def sample_registry() -> dict:
    return {
        "characters": [
            {"character_id": "C001", "name": "Mira", "aliases": []},
            {"character_id": "C002", "name": "Rowan", "aliases": []},
        ],
        "locations": [
            {"location_id": "L001", "name": "archive", "aliases": []},
        ],
        "relationship_map": [
            {
                "from_character_id": "C001",
                "to_character_id": "C002",
                "relationship": "Mira suspects Rowan is hiding evidence.",
            }
        ],
    }


def bootstrap_payload() -> dict:
    return {
        "novel_text": sample_novel_text(),
        "title": "Harbor Case",
        "registry": sample_registry(),
        "profile_id": "female_revenge_vertical",
    }


def test_bootstrap_returns_project_state_with_chunks(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)

    response = client.post("/api/v1/project/bootstrap", json=bootstrap_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"].startswith("project:")
    assert data["novel"]["title"] == "Harbor Case"
    assert Registry.model_validate(data["registry"]).characters[0].name == "Mira"

    store = EvidenceStore.from_json(data["evidence_store"])
    assert [chunk.chunk_id for chunk in store.list_by_tag()] == [
        "CH001:p1-1",
        "CH001:p2-2",
    ]


def test_diagnose_endpoint_replay_fills_diagnosis(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)
    state = bootstrap_state(client)

    response = client.post(
        "/api/v1/diagnose",
        json={**state, "profile_id": "female_revenge_vertical"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ip_diagnosis"]["recommended_profile_id"] == "female_revenge_vertical"
    assert data["story_bible"] is None
    assert data["evidence_store"] == state["evidence_store"]


def test_story_bible_endpoint_replay_fills_bible_and_indexes(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)
    state = bootstrap_state(client)

    response = client.post(
        "/api/v1/story-bible",
        json={**state, "existing_bible": None},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["story_bible"]["premise"]["text"]
    assert data["ip_diagnosis"] is None

    store = EvidenceStore.from_json(data["evidence_store"])
    assert {
        chunk.chunk_id for chunk in store.list_by_tag(event_tag="story_bible")
    } >= {"story_bible:premise", "story_bible:core_hook"}


def test_project_state_json_roundtrip(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)
    state = bootstrap_state(client)

    from app.api.project_state import ProjectState

    model = ProjectState.model_validate(state)
    round_tripped = ProjectState.model_validate_json(model.model_dump_json())

    assert round_tripped.model_dump(mode="json") == model.model_dump(mode="json")


def bootstrap_state(client: TestClient) -> dict:
    response = client.post("/api/v1/project/bootstrap", json=bootstrap_payload())
    assert response.status_code == 200
    return response.json()


def forbid_live_api(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("V1 API replay must not call live API")
        ),
    )
