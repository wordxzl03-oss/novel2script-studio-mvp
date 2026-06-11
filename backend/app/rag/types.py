from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schema.short_drama import SourceLink, StrictModel

EvidenceSourceType = Literal[
    "novel",
    "story_bible",
    "registry",
    "profile",
    "adaptation_log",
    "override",
    "script",
]


class EvidenceMetadata(StrictModel):
    chapter_id: str | None = None
    para_range: tuple[int, int] | None = None
    episode_id: str | None = None
    scene_id: str | None = None
    element_id: str | None = None
    character_ids: list[str] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    event_tags: list[str] = Field(default_factory=list)
    conflict_type: str | None = None
    emotional_tone: str | None = None
    source_hash: str | None = None


class EvidenceChunk(StrictModel):
    chunk_id: str = Field(min_length=1)
    source_type: EvidenceSourceType
    source_ref: SourceLink | None = None
    text: str = Field(min_length=1)
    metadata: EvidenceMetadata


class RetrievalContext(StrictModel):
    task_name: str = Field(min_length=1)
    query: str = Field(min_length=1)
    filters: dict[str, Any]
    evidence_chunks: list[EvidenceChunk] = Field(min_length=1)
    locked_items: dict[str, Any]
    profile_context: dict[str, Any]
    project_memory: list[dict[str, Any]]
