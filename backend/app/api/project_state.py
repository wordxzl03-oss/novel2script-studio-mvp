from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schema.short_drama import (
    IPDiagnosis,
    Registry,
    Series,
    SourceNovel,
    StoryBible,
    StrictModel,
)


class ProjectState(StrictModel):
    """Stateless V1 project payload held by the frontend."""

    project_id: str = Field(min_length=1)
    novel: SourceNovel
    registry: Registry = Field(default_factory=Registry)
    evidence_store: dict[str, Any] = Field(default_factory=lambda: {"chunks": []})
    series: Series | None = None
    ip_diagnosis: IPDiagnosis | None = None
    story_bible: StoryBible | None = None
