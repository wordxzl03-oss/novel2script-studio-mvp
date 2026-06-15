from __future__ import annotations

from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import retrieve_by_tags
from app.schema.short_drama import EvidenceMeta, EvidenceText, StoryBible


def evidence(text: str, *, user_locked: bool = False) -> EvidenceText:
    return EvidenceText(
        text=text,
        evidence=EvidenceMeta(
            source_basis=[],
            confidence=0.8,
            is_inferred=True,
            user_locked=user_locked,
        ),
    )


def sample_bible() -> StoryBible:
    return StoryBible(
        premise=evidence("Mira reopens a buried case after finding a letter."),
        core_hook=evidence("A hidden letter forces Mira to confront Rowan."),
        themes=[evidence("Hidden evidence demands a public reckoning.")],
        character_arcs=[evidence("Mira moves from discovery to pursuit.")],
        major_reveals=[evidence("Rowan hid the letter before dawn.")],
    )


def test_index_story_bible_adds_story_bible_chunks():
    from app.rag.bible_index import index_story_bible

    store = EvidenceStore()

    chunks = index_story_bible(sample_bible(), store)

    assert [chunk.chunk_id for chunk in chunks] == [
        "story_bible:premise",
        "story_bible:core_hook",
        "story_bible:themes:1",
        "story_bible:character_arcs:1",
        "story_bible:major_reveals:1",
    ]
    assert all(chunk.source_type == "story_bible" for chunk in chunks)
    premise_chunk = store.get("story_bible:premise")
    assert premise_chunk is not None
    assert premise_chunk.text == sample_bible().premise.text
    assert premise_chunk.metadata.event_tags == ["story_bible", "premise"]
    assert premise_chunk.metadata.source_hash is not None


def test_indexed_bible_chunk_is_retrievable():
    from app.rag.bible_index import index_story_bible

    store = EvidenceStore()
    index_story_bible(sample_bible(), store)

    chunks = retrieve_by_tags(store, {"event_tags": ["story_bible"]})

    assert {chunk.chunk_id for chunk in chunks} == {
        "story_bible:premise",
        "story_bible:core_hook",
        "story_bible:themes:1",
        "story_bible:character_arcs:1",
        "story_bible:major_reveals:1",
    }
    assert store.get("story_bible:major_reveals:1") is not None
