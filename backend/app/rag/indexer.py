from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.types import EvidenceChunk


@dataclass(frozen=True)
class EvidenceIndex:
    character_ids: dict[str, list[str]] = field(default_factory=dict)
    location_ids: dict[str, list[str]] = field(default_factory=dict)
    event_tags: dict[str, list[str]] = field(default_factory=dict)


def build_inverted_index(chunks: list[EvidenceChunk]) -> EvidenceIndex:
    character_ids: dict[str, list[str]] = {}
    location_ids: dict[str, list[str]] = {}
    event_tags: dict[str, list[str]] = {}

    for chunk in chunks:
        for character_id in chunk.metadata.character_ids:
            _append_unique(character_ids, character_id, chunk.chunk_id)
        for location_id in chunk.metadata.location_ids:
            _append_unique(location_ids, location_id, chunk.chunk_id)
        for event_tag in chunk.metadata.event_tags:
            _append_unique(event_tags, event_tag, chunk.chunk_id)

    return EvidenceIndex(
        character_ids=character_ids,
        location_ids=location_ids,
        event_tags=event_tags,
    )


def _append_unique(index: dict[str, list[str]], key: str, chunk_id: str) -> None:
    if not key:
        return

    chunk_ids = index.setdefault(key, [])
    if chunk_id not in chunk_ids:
        chunk_ids.append(chunk_id)
