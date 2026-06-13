from __future__ import annotations

from typing import Any

from app.rag.indexer import EvidenceIndex, build_inverted_index
from app.rag.types import EvidenceChunk


class EvidenceStore:
    def __init__(self) -> None:
        self._chunks_by_id: dict[str, EvidenceChunk] = {}
        self._index = EvidenceIndex()

    def add_chunks(self, chunks: list[EvidenceChunk]) -> None:
        for chunk in chunks:
            self._chunks_by_id[chunk.chunk_id] = chunk
        self._rebuild_index()

    def get(self, chunk_id: str) -> EvidenceChunk | None:
        return self._chunks_by_id.get(chunk_id)

    def get_by_range(
        self, chapter_id: str, para_range: tuple[int, int]
    ) -> list[EvidenceChunk]:
        start_para, end_para = para_range
        matches = [
            chunk
            for chunk in self._chunks_by_id.values()
            if _chunk_overlaps_range(chunk, chapter_id, start_para, end_para)
        ]
        return sorted(matches, key=_chunk_sort_key)

    def list_by_tag(
        self,
        *,
        character_id: str | None = None,
        location_id: str | None = None,
        event_tag: str | None = None,
    ) -> list[EvidenceChunk]:
        selected_sets: list[set[str]] = []
        if character_id is not None:
            selected_sets.append(set(self._index.character_ids.get(character_id, [])))
        if location_id is not None:
            selected_sets.append(set(self._index.location_ids.get(location_id, [])))
        if event_tag is not None:
            selected_sets.append(set(self._index.event_tags.get(event_tag, [])))

        if not selected_sets:
            return sorted(self._chunks_by_id.values(), key=_chunk_sort_key)

        chunk_ids = set.intersection(*selected_sets)
        chunks = [self._chunks_by_id[chunk_id] for chunk_id in chunk_ids]
        return sorted(chunks, key=_chunk_sort_key)

    def to_json(self) -> dict[str, Any]:
        return {
            "chunks": [
                chunk.model_dump(mode="json")
                for chunk in sorted(self._chunks_by_id.values(), key=_chunk_sort_key)
            ]
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "EvidenceStore":
        store = cls()
        store.add_chunks(
            [
                chunk
                if isinstance(chunk, EvidenceChunk)
                else EvidenceChunk.model_validate(chunk)
                for chunk in data.get("chunks", [])
            ]
        )
        return store

    def _rebuild_index(self) -> None:
        self._index = build_inverted_index(list(self._chunks_by_id.values()))


def _chunk_overlaps_range(
    chunk: EvidenceChunk, chapter_id: str, start_para: int, end_para: int
) -> bool:
    if chunk.source_type != "novel":
        return False
    if chunk.metadata.chapter_id != chapter_id:
        return False
    if chunk.metadata.para_range is None:
        return False

    chunk_start, chunk_end = chunk.metadata.para_range
    return chunk_start <= end_para and start_para <= chunk_end


def _chunk_sort_key(chunk: EvidenceChunk) -> tuple[str, int, int, str]:
    chapter_id = chunk.metadata.chapter_id or ""
    para_range = chunk.metadata.para_range or (0, 0)
    return (chapter_id, para_range[0], para_range[1], chunk.chunk_id)
