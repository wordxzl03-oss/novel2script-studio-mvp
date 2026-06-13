from __future__ import annotations

import hashlib

from app.rag.types import EvidenceChunk, EvidenceMetadata
from app.schema.short_drama import Registry, SourceLink, SourceNovel, SourceRange


def normalize_source_text(text: str) -> str:
    return text.strip()


def source_hash_for_text(text: str) -> str:
    normalized = normalize_source_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_novel(novel: SourceNovel, registry: Registry | None = None) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []

    for chapter in novel.chapters:
        for para_index, paragraph in enumerate(chapter.paragraphs, start=1):
            text = normalize_source_text(paragraph)
            if not text:
                continue

            source_range = SourceRange(
                chapter_id=chapter.chapter_id,
                start_para=para_index,
                end_para=para_index,
            )
            chunks.append(
                EvidenceChunk(
                    chunk_id=f"{chapter.chapter_id}:p{para_index}-{para_index}",
                    source_type="novel",
                    source_ref=SourceLink(type="source_based", source_range=source_range),
                    text=text,
                    metadata=EvidenceMetadata(
                        chapter_id=chapter.chapter_id,
                        para_range=(para_index, para_index),
                        character_ids=_matching_character_ids(text, registry),
                        location_ids=_matching_location_ids(text, registry),
                        source_hash=source_hash_for_text(text),
                    ),
                )
            )

    return chunks


def _matching_character_ids(text: str, registry: Registry | None) -> list[str]:
    if registry is None:
        return []

    return [
        character.character_id
        for character in registry.characters
        if _matches_any_term(text, [character.name, *character.aliases])
    ]


def _matching_location_ids(text: str, registry: Registry | None) -> list[str]:
    if registry is None:
        return []

    return [
        location.location_id
        for location in registry.locations
        if _matches_any_term(text, [location.name, *location.aliases])
    ]


def _matches_any_term(text: str, terms: list[str]) -> bool:
    return any(term.strip() and term.strip() in text for term in terms)
