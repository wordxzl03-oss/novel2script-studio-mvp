from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk, EvidenceMetadata
from app.schema.short_drama import SourceLink, SourceRange


PROFILE_ID = "female_revenge_vertical"


def sample_novel_text() -> str:
    return "\n".join(
        [
            "Mira finds a sealed letter and decides to reopen the case.",
            "Rowan hides the letter in the archive before dawn.",
            "Mira confronts Rowan at the pier and records his confession.",
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
            {"location_id": "L002", "name": "pier", "aliases": []},
        ],
        "relationship_map": [
            {
                "from_character_id": "C001",
                "to_character_id": "C002",
                "relationship": "Mira suspects Rowan is hiding evidence.",
            }
        ],
    }


def test_plan_endpoint_replay_fills_outlines(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)
    state = project_state_with_story_bible_evidence(client)

    response = client.post(
        "/api/v1/plan",
        json={**state, "profile_id": PROFILE_ID},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["series"]["series_id"] == "SRS001"
    assert data["series"]["title"] == "Harbor Case Planner Agent"
    assert len(data["series"]["outlines"]) == 10
    assert data["series"]["outlines"][0]["number"] == 1
    assert data["series"]["episodes"][0]["episode_id"] == "E000"


def test_write_endpoint_replay_writes_three_episodes(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)
    planned = planned_state(client)

    response = client.post(
        "/api/v1/write",
        json={**planned, "profile_id": PROFILE_ID, "max_episodes": 3},
    )

    assert response.status_code == 200
    data = response.json()
    episodes = data["series"]["episodes"]
    assert [episode["number"] for episode in episodes] == [1, 2, 3]
    assert all(episode["scenes"] for episode in episodes)
    assert all(episode["retention_points"] for episode in episodes)


def test_episode_highlight_endpoint_returns_anchors_and_compression(monkeypatch):
    forbid_live_api(monkeypatch)
    client = TestClient(app)
    written = written_state(client)

    response = client.post(
        "/api/v1/episode-highlight",
        json={**written, "episode_number": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["highlight_anchors"][0]["chapter_id"] == "CH001"
    assert data["highlight_anchors"][0]["para_range"] == [1, 1]
    assert data["compression_view"][0]["resolved_text"] == (
        "Mira finds a sealed letter and decides to reopen the case."
    )
    assert data["element_badges"]
    assert all(item["badges"] for item in data["element_badges"])


def planned_state(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/plan",
        json={
            **project_state_with_story_bible_evidence(client),
            "profile_id": PROFILE_ID,
        },
    )
    assert response.status_code == 200
    return response.json()


def written_state(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/write",
        json={**planned_state(client), "profile_id": PROFILE_ID, "max_episodes": 3},
    )
    assert response.status_code == 200
    return response.json()


def project_state_with_story_bible_evidence(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/project/bootstrap",
        json={
            "novel_text": sample_novel_text(),
            "title": "Harbor Case Planner Agent",
            "registry": sample_registry(),
            "profile_id": PROFILE_ID,
        },
    )
    assert response.status_code == 200
    state = response.json()

    store = EvidenceStore.from_json(state["evidence_store"])
    store.add_chunks([story_bible_chunk()])
    state["evidence_store"] = store.to_json()
    return state


def story_bible_chunk() -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id="story_bible:premise",
        source_type="story_bible",
        source_ref=source_link(1, 3),
        text=(
            "Mira's investigation escalates from a hidden letter to a public "
            "confrontation with Rowan."
        ),
        metadata=EvidenceMetadata(
            event_tags=["story_bible"],
            chapter_id="CH001",
            para_range=(1, 3),
            character_ids=["C001", "C002"],
            location_ids=["L001", "L002"],
        ),
    )


def source_link(start_para: int, end_para: int | None = None) -> SourceLink:
    return SourceLink(
        type="source_based",
        source_range=SourceRange(
            chapter_id="CH001",
            start_para=start_para,
            end_para=end_para or start_para,
        ),
    )


def forbid_live_api(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("V1 episode API replay must not call live API")
        ),
    )
