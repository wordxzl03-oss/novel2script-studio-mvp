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


def test_deterministic_retrieval_by_source_ranges():
    from app.rag.retriever import retrieve_deterministic

    chunks = retrieve_deterministic(
        sample_store(),
        [SourceRange(chapter_id="CH001", start_para=2, end_para=3)],
    )

    assert [chunk.chunk_id for chunk in chunks] == ["CH001:p2-2", "CH001:p3-3"]


def test_tag_retrieval_by_character():
    from app.rag.retriever import retrieve_by_tags

    chunks = retrieve_by_tags(sample_store(), {"character_ids": ["C002"]})

    assert [chunk.chunk_id for chunk in chunks] == ["CH001:p2-2", "CH001:p3-3"]


def test_tag_retrieval_by_keyword_substring():
    from app.rag.retriever import retrieve_by_tags

    chunks = retrieve_by_tags(sample_store(), {"keywords": ["archive"]})

    assert [chunk.chunk_id for chunk in chunks] == ["CH001:p3-3"]


def test_build_context_raises_on_empty_retrieval():
    from app.rag.retriever import EmptyRetrievalError, build_retrieval_context

    with pytest.raises(EmptyRetrievalError, match="no evidence chunks"):
        build_retrieval_context(
            task_name="episode_writer",
            query="write episode 1",
            store=sample_store(),
            source_ranges=[SourceRange(chapter_id="CH001", start_para=9, end_para=9)],
        )


def test_build_context_returns_valid_retrieval_context():
    from app.rag.retriever import build_retrieval_context
    from app.rag.types import RetrievalContext

    context = build_retrieval_context(
        task_name="episode_writer",
        query="write episode 1",
        store=sample_store(),
        source_ranges=[SourceRange(chapter_id="CH001", start_para=1, end_para=1)],
        filters={"character_ids": ["C002"]},
        locked_items={"cliffhanger": "locked"},
        profile_context={"tone": "fast"},
        project_memory=[{"note": "draft"}],
    )

    assert isinstance(context, RetrievalContext)
    assert [chunk.chunk_id for chunk in context.evidence_chunks] == [
        "CH001:p1-1",
        "CH001:p2-2",
        "CH001:p3-3",
    ]
    assert context.filters == {"character_ids": ["C002"]}
    assert context.locked_items == {"cliffhanger": "locked"}
    assert context.profile_context == {"tone": "fast"}
    assert context.project_memory == [{"note": "draft"}]


def test_source_ranges_of_episode_extracts_nested_source_ranges():
    from app.rag.retriever import source_ranges_of

    source_range = SourceRange(chapter_id="CH001", start_para=1, end_para=2)
    episode = Episode.model_validate(
        {
            "episode_id": "E001",
            "number": 1,
            "opening_hook": "A letter arrives.",
            "main_conflict": "Mira must choose whom to trust.",
            "emotional_payoff": "Rowan admits the truth.",
            "cliffhanger": "The archive door opens.",
            "source_ranges": [
                SourceLink(type="source_based", source_range=source_range).model_dump(),
                SourceLink(
                    type="invented_for_adaptation",
                    reason="Bridge scene for pacing.",
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

    assert source_ranges_of(episode) == [source_range]


def test_semantic_retrieval_not_implemented_in_v1():
    from app.rag.retriever import retrieve_semantic

    with pytest.raises(NotImplementedError, match="embedding"):
        retrieve_semantic(sample_store(), query="archive")


def test_rag_package_exports_retriever_symbols():
    from app.rag import (
        EmptyRetrievalError,
        build_retrieval_context,
        retrieve_by_tags,
        retrieve_deterministic,
        retrieve_semantic,
        source_ranges_of,
    )

    assert EmptyRetrievalError
    assert build_retrieval_context
    assert retrieve_by_tags
    assert retrieve_deterministic
    assert retrieve_semantic
    assert source_ranges_of
