from __future__ import annotations

from collections.abc import Iterable

from app.rag.chunker import source_hash_for_text
from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk, EvidenceMetadata
from app.schema.short_drama import EvidenceText, StoryBible


def index_story_bible(bible: StoryBible, store: EvidenceStore) -> list[EvidenceChunk]:
    chunks = [
        _chunk_for(section, index, item)
        for section, index, item in _iter_story_bible_items(bible)
    ]
    store.add_chunks(chunks)
    return chunks


def _iter_story_bible_items(
    bible: StoryBible,
) -> Iterable[tuple[str, int | None, EvidenceText]]:
    if bible.premise is not None:
        yield "premise", None, bible.premise
    if bible.core_hook is not None:
        yield "core_hook", None, bible.core_hook

    for section in ("themes", "character_arcs", "major_reveals"):
        items = getattr(bible, section)
        for index, item in enumerate(items, start=1):
            yield section, index, item


def _chunk_for(
    section: str, index: int | None, item: EvidenceText
) -> EvidenceChunk:
    chunk_id = f"story_bible:{section}"
    if index is not None:
        chunk_id = f"{chunk_id}:{index}"

    return EvidenceChunk(
        chunk_id=chunk_id,
        source_type="story_bible",
        source_ref=None,
        text=item.text,
        metadata=EvidenceMetadata(
            event_tags=["story_bible", section],
            source_hash=source_hash_for_text(item.text),
        ),
    )
