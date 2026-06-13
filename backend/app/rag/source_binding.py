from __future__ import annotations

from typing import Any

from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk
from app.schema.short_drama import Episode, SourceLink, SourceRange


def bind_source_ranges(
    episode: Episode, source_links: list[SourceLink], store: EvidenceStore
) -> Episode:
    if not source_links:
        raise ValueError("episode.source_ranges requires at least one source link")

    for source_link in source_links:
        if source_link.source_range is None:
            continue
        _require_resolved(source_link.source_range, store)

    return episode.model_copy(update={"source_ranges": list(source_links)})


def resolve_episode_sources(
    episode: Episode, store: EvidenceStore
) -> list[dict[str, Any]]:
    resolved_sources: list[dict[str, Any]] = []
    for source_link in episode.source_ranges:
        source_range = source_link.source_range
        resolved_text = None
        if source_range is not None:
            resolved_text = _require_resolved(source_range, store)

        resolved_sources.append(
            {
                "source_link": source_link,
                "source_range": source_range,
                "resolved_text": resolved_text,
                "source_type": source_link.type,
            }
        )

    return resolved_sources


def _require_resolved(source_range: SourceRange, store: EvidenceStore) -> str:
    source_text = _resolve_source_text(source_range, store)
    if source_text is None:
        raise ValueError(
            "source_range "
            f"{source_range.chapter_id}:{source_range.start_para}-{source_range.end_para} "
            "could not be resolved from evidence store"
        )
    return source_text


def _resolve_source_text(source_range: SourceRange, store: EvidenceStore) -> str | None:
    chunks = store.get_by_range(
        source_range.chapter_id,
        (source_range.start_para, source_range.end_para),
    )
    if not chunks:
        return None
    if not _source_range_is_fully_covered(source_range, chunks):
        return None
    return "\n".join(chunk.text for chunk in chunks)


def _source_range_is_fully_covered(
    source_range: SourceRange, chunks: list[EvidenceChunk]
) -> bool:
    covered_paras: set[int] = set()
    for chunk in chunks:
        if chunk.metadata.para_range is None:
            continue
        chunk_start, chunk_end = chunk.metadata.para_range
        covered_paras.update(range(chunk_start, chunk_end + 1))

    expected_paras = set(range(source_range.start_para, source_range.end_para + 1))
    return expected_paras.issubset(covered_paras)
