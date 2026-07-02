from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.project_state import ProjectState
from app.main import app


PROFILE_ID = "female_revenge_vertical"


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


def test_v1_replay_flow_reaches_written_episode_highlight(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)

    state = post_state(
        client,
        "/api/v1/project/bootstrap",
        {
            "novel_text": sample_novel_text(),
            "title": "Harbor Case",
            "registry": sample_registry(),
            "profile_id": PROFILE_ID,
        },
    )
    assert state["novel"]["title"] == "Harbor Case"

    state = post_state(client, "/api/v1/diagnose", {**state, "profile_id": PROFILE_ID})
    assert state["ip_diagnosis"]["recommended_profile_id"] == PROFILE_ID

    state = post_state(client, "/api/v1/story-bible", {**state, "existing_bible": None})
    assert state["story_bible"]["premise"]["text"]

    state = post_state(client, "/api/v1/plan", {**state, "profile_id": PROFILE_ID})
    assert len(state["series"]["outlines"]) >= 1

    state = post_state(
        client,
        "/api/v1/write",
        {**state, "profile_id": PROFILE_ID, "max_episodes": 3},
    )
    assert len(state["series"]["episodes"]) == 3

    highlight_response = client.post(
        "/api/v1/episode-highlight",
        json={**state, "episode_number": 1},
    )
    assert highlight_response.status_code == 200
    highlight = highlight_response.json()
    assert highlight["highlight_anchors"]
    assert highlight["compression_view"]
    assert highlight["element_badges"]


def post_state(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.json()
    data = response.json()
    ProjectState.model_validate(data)
    return data


def forbid_live_api(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("V1 smoke replay must not call live API")
        ),
    )
