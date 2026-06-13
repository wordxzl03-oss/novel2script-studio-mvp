from __future__ import annotations

from typing import Any

from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk, RetrievalContext
from app.schema.short_drama import Episode, SourceRange


class EmptyRetrievalError(ValueError):
    pass


def retrieve_deterministic(
    store: EvidenceStore, source_ranges: list[SourceRange]
) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    seen_chunk_ids: set[str] = set()

    for source_range in source_ranges:
        range_chunks = store.get_by_range(
            source_range.chapter_id,
            (source_range.start_para, source_range.end_para),
        )
        for chunk in range_chunks:
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            chunks.append(chunk)

    return chunks


def retrieve_by_tags(store: EvidenceStore, filters: dict) -> list[EvidenceChunk]:
    selected_chunk_id_sets: list[set[str]] = []

    character_ids = _as_list(filters.get("character_ids"))
    if character_ids:
        selected_chunk_id_sets.append(
            {
                chunk.chunk_id
                for character_id in character_ids
                for chunk in store.list_by_tag(character_id=character_id)
            }
        )

    location_ids = _as_list(filters.get("location_ids"))
    if location_ids:
        selected_chunk_id_sets.append(
            {
                chunk.chunk_id
                for location_id in location_ids
                for chunk in store.list_by_tag(location_id=location_id)
            }
        )

    event_tags = _as_list(filters.get("event_tags"))
    if event_tags:
        selected_chunk_id_sets.append(
            {
                chunk.chunk_id
                for event_tag in event_tags
                for chunk in store.list_by_tag(event_tag=event_tag)
            }
        )

    keywords = _as_list(filters.get("keywords"))
    if keywords:
        selected_chunk_id_sets.append(
            {
                chunk.chunk_id
                for chunk in store.list_by_tag()
                if any(keyword in chunk.text for keyword in keywords)
            }
        )

    if not selected_chunk_id_sets:
        return []

    selected_chunk_ids = set.intersection(*selected_chunk_id_sets)
    return [
        chunk for chunk in store.list_by_tag() if chunk.chunk_id in selected_chunk_ids
    ]


def source_ranges_of(episode: Episode) -> list[SourceRange]:
    return [
        source_link.source_range
        for source_link in episode.source_ranges
        if source_link.source_range is not None
    ]


def build_retrieval_context(
    *,
    task_name: str,
    query: str,
    store: EvidenceStore,
    source_ranges: list[SourceRange] | None = None,
    filters: dict[str, Any] | None = None,
    locked_items: dict[str, Any] | None = None,
    profile_context: dict[str, Any] | None = None,
    project_memory: list[dict[str, Any]] | None = None,
) -> RetrievalContext:
    evidence_chunks = _merge_chunks(
        retrieve_deterministic(store, source_ranges or []),
        retrieve_by_tags(store, filters or {}),
    )
    if not evidence_chunks:
        raise EmptyRetrievalError("retrieval returned no evidence chunks")

    return RetrievalContext(
        task_name=task_name,
        query=query,
        filters=filters or {},
        evidence_chunks=evidence_chunks,
        locked_items=locked_items or {},
        profile_context=profile_context or {},
        project_memory=project_memory or [],
    )


def retrieve_semantic(*args: object, **kwargs: object) -> list[EvidenceChunk]:
    raise NotImplementedError(
        "embedding/vector retrieval is outside V1 scope; interface reserved"
    )


def _merge_chunks(*chunk_groups: list[EvidenceChunk]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    seen_chunk_ids: set[str] = set()

    for chunk_group in chunk_groups:
        for chunk in chunk_group:
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            chunks.append(chunk)

    return chunks


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [item for item in value if isinstance(item, str)]
