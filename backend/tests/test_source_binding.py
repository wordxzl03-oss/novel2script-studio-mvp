import pytest

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


def source_based(start: int, end: int | None = None) -> SourceLink:
    return SourceLink(type="source_based", source_range=source_range(start, end))


def sample_episode() -> Episode:
    return Episode.model_validate(
        {
            "episode_id": "E001",
            "number": 1,
            "opening_hook": "A letter arrives.",
            "main_conflict": "Mira must choose whom to trust.",
            "emotional_payoff": "Rowan admits the truth.",
            "cliffhanger": "The archive door opens.",
            "source_ranges": [source_based(1).model_dump()],
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


def test_bind_multiple_ranges_preserves_order():
    from app.rag.source_binding import bind_source_ranges

    episode = sample_episode()
    links = [
        source_based(2),
        SourceLink(
            type="literal_quote",
            source_range=source_range(3),
            quote="Rowan hides the letter in the archive.",
        ),
        SourceLink(
            type="invented_for_adaptation",
            reason="Bridge scene for short-drama pacing.",
        ),
    ]

    updated = bind_source_ranges(episode, links, sample_store())

    assert updated.source_ranges == links
    assert episode.source_ranges == [source_based(1)]


def test_resolve_returns_text_and_source_type_per_segment():
    from app.rag.source_binding import resolve_episode_sources

    links = [
        source_based(2, 3),
        SourceLink(
            type="invented_for_adaptation",
            reason="Bridge scene for short-drama pacing.",
        ),
    ]
    episode = sample_episode().model_copy(update={"source_ranges": links})

    resolved = resolve_episode_sources(episode, sample_store())

    assert [item["source_type"] for item in resolved] == [
        "source_based",
        "invented_for_adaptation",
    ]
    assert resolved[0]["source_link"] == links[0]
    assert resolved[0]["source_range"] == source_range(2, 3)
    assert resolved[0]["resolved_text"] == (
        "Mira meets Rowan at the pier.\n"
        "Rowan hides the letter in the archive."
    )
    assert resolved[1]["source_link"] == links[1]
    assert resolved[1]["source_range"] is None
    assert resolved[1]["resolved_text"] is None


def test_bind_unresolvable_range_errors():
    from app.rag.source_binding import bind_source_ranges

    missing = SourceLink(
        type="source_based",
        source_range=SourceRange(chapter_id="CH001", start_para=9, end_para=9),
    )

    with pytest.raises(ValueError, match="CH001:9-9"):
        bind_source_ranges(sample_episode(), [missing], sample_store())


def test_source_ranges_survive_roundtrip():
    from app.rag.source_binding import bind_source_ranges

    links = [
        source_based(1),
        source_based(2, 3),
        SourceLink(
            type="invented_for_adaptation",
            reason="Bridge scene for short-drama pacing.",
        ),
    ]

    updated = bind_source_ranges(sample_episode(), links, sample_store())
    restored = Episode.model_validate(updated.model_dump(mode="json"))

    assert restored.source_ranges == links
