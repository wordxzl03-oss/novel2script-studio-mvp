from fastapi.testclient import TestClient

from app.ai.task import ValidationFinding
from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.schema.short_drama import (
    Episode,
    Registry,
    SourceChapter,
    SourceLink,
    SourceNovel,
    SourceRange,
)
from app.validation.source_validation import SourceLinkVerdict


def sample_novel() -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "Mira finds a sealed letter.",
                    "Mira meets Rowan at the pier.",
                    "Rowan hides the letter in the archive.",
                ],
            )
        ],
    )


def sample_registry() -> Registry:
    return Registry.model_validate(
        {
            "characters": [
                {"character_id": "C001", "name": "Mira", "aliases": []},
                {"character_id": "C002", "name": "Rowan", "aliases": []},
            ],
            "locations": [
                {"location_id": "L001", "name": "pier", "aliases": []},
                {"location_id": "L002", "name": "archive", "aliases": []},
            ],
        }
    )


def sample_store() -> EvidenceStore:
    store = EvidenceStore()
    store.add_chunks(chunk_novel(sample_novel(), registry=sample_registry()))
    return store


def source_range(start: int, end: int | None = None) -> SourceRange:
    return SourceRange(chapter_id="CH001", start_para=start, end_para=end or start)


def sample_episode() -> Episode:
    return Episode.model_validate(
        {
            "episode_id": "E001",
            "number": 1,
            "opening_hook": "A letter arrives.",
            "main_conflict": "Mira must choose whom to trust.",
            "emotional_payoff": "Rowan admits the truth.",
            "cliffhanger": "The archive door opens.",
            "source_ranges": [
                SourceLink(
                    type="literal_quote",
                    source_range=source_range(1),
                    quote="Mira finds a sealed letter.",
                ).model_dump(),
                SourceLink(type="source_based", source_range=source_range(2, 3)).model_dump(),
                SourceLink(
                    type="invented_for_adaptation",
                    reason="Bridge scene for short-drama pacing.",
                ).model_dump(),
            ],
            "scenes": [
                {
                    "scene_id": "S001",
                    "beats": [
                        {
                            "beat_id": "B001",
                            "elements": [
                                {
                                    "element_id": "A001",
                                    "type": "action",
                                    "text": "Mira reads the letter.",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def verdict(
    *,
    resolved: bool,
    verbatim_ok: bool | None,
    suggested_action: str = "accept",
) -> SourceLinkVerdict:
    finding = None
    if not resolved or verbatim_ok is False:
        finding = ValidationFinding(
            code="test",
            severity="error",
            message="test finding",
        )
    return SourceLinkVerdict(
        resolved=resolved,
        verbatim_ok=verbatim_ok,
        suggested_action=suggested_action,
        finding=finding,
    )


def test_badge_state_four_cases():
    from app.validation.highlight import derive_badge_state

    literal = SourceLink(
        type="literal_quote",
        source_range=source_range(1),
        quote="Mira finds a sealed letter.",
    )
    source_based = SourceLink(type="source_based", source_range=source_range(2))
    invented = SourceLink(
        type="invented_for_adaptation",
        reason="Bridge scene for short-drama pacing.",
    )

    assert derive_badge_state(verdict(resolved=True, verbatim_ok=True), literal) == "literal_ok"
    assert derive_badge_state(verdict(resolved=True, verbatim_ok=None), source_based) == "source_based"
    assert derive_badge_state(verdict(resolved=True, verbatim_ok=None), invented) == "invented"
    assert derive_badge_state(verdict(resolved=False, verbatim_ok=None), source_based) == "unverified"
    assert derive_badge_state(verdict(resolved=True, verbatim_ok=False), literal) == "unverified"


def test_highlight_anchors_match_source_links():
    from app.validation.highlight import compute_highlight_anchors

    anchors = compute_highlight_anchors(sample_episode(), sample_store())

    assert anchors == [
        {
            "chapter_id": "CH001",
            "para_range": (1, 1),
            "badge_state": "literal_ok",
            "source_link": sample_episode().source_ranges[0],
        },
        {
            "chapter_id": "CH001",
            "para_range": (2, 3),
            "badge_state": "source_based",
            "source_link": sample_episode().source_ranges[1],
        },
    ]


def test_compression_view_lists_all_sources_in_order():
    from app.validation.highlight import compute_compression_view

    view = compute_compression_view(sample_episode(), sample_store())

    assert [item["source_type"] for item in view] == [
        "literal_quote",
        "source_based",
        "invented_for_adaptation",
    ]
    assert view[0]["text_excerpt"] == "Mira finds a sealed letter."
    assert view[1]["text_excerpt"] == (
        "Mira meets Rowan at the pier.\n"
        "Rowan hides the letter in the archive."
    )
    assert view[2]["text_excerpt"] is None


def test_element_badges_cover_every_script_element():
    from app.validation.highlight import compute_element_badges

    episode_data = sample_episode().model_dump(mode="json")
    source_links = episode_data["source_ranges"]
    episode_data["scenes"][0]["beats"][0]["elements"] = [
        {
            "element_id": "A001",
            "type": "action",
            "text": "Mira reads the letter.",
            "source_links": [source_links[0]],
        },
        {
            "element_id": "A002",
            "type": "action",
            "text": "Mira crosses the pier.",
            "source_links": [source_links[1]],
        },
        {
            "element_id": "A003",
            "type": "action",
            "text": "A bridge beat connects the scenes.",
            "source_links": [source_links[2]],
        },
        {
            "element_id": "A004",
            "type": "action",
            "text": "This element has no source link.",
        },
    ]

    badges = compute_element_badges(Episode.model_validate(episode_data), sample_store())

    assert [item["element_id"] for item in badges] == ["A001", "A002", "A003", "A004"]
    assert [item["badges"][0]["badge_state"] for item in badges] == [
        "literal_ok",
        "source_based",
        "invented",
        "unverified",
    ]
    assert badges[0]["badges"][0]["para_range"] == (1, 1)
    assert badges[2]["badges"][0]["reason"] == "Bridge scene for short-drama pacing."
    assert badges[3]["badges"][0]["source_link"] is None


def test_endpoints_are_read_only():
    from app.api.routes import get_llm_client
    from app.main import app

    def fail_if_generation_dependency_runs():
        raise AssertionError("highlight preview must not create an LLM client")

    app.dependency_overrides[get_llm_client] = fail_if_generation_dependency_runs
    client = TestClient(app)

    response = client.request(
        "GET",
        "/api/highlight-preview",
        json={
            "episode": sample_episode().model_dump(mode="json"),
            "evidence_store": sample_store().to_json(),
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["highlight_anchors"][0]["badge_state"] == "literal_ok"
    assert [item["source_type"] for item in payload["compression_view"]] == [
        "literal_quote",
        "source_based",
        "invented_for_adaptation",
    ]
    assert payload["element_badges"][0]["element_id"] == "A001"
