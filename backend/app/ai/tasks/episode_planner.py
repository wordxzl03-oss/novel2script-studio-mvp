from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.ai.structured_task import StructuredGenerationTask
from app.ai.task import ValidationFinding
from app.profiles.loader import ShortDramaProfile, profile_to_context
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import EpisodeOutlinePlan, Registry
from app.validation.short_drama_linter import lint_outline


class EpisodePlannerTask(StructuredGenerationTask):
    output_model = EpisodeOutlinePlan
    temperature = 0.2

    def __init__(
        self,
        *,
        registry: Registry,
        profile: ShortDramaProfile,
        **kwargs: Any,
    ) -> None:
        self.registry = registry
        self.profile = profile
        super().__init__(**kwargs)

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "task": "episode_planner",
            "query": retrieval_context.query,
            "filters": retrieval_context.filters,
            "evidence_chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "source_type": chunk.source_type,
                    "source_ref": (
                        chunk.source_ref.model_dump(mode="json")
                        if chunk.source_ref is not None
                        else None
                    ),
                    "text": chunk.text,
                    "metadata": chunk.metadata.model_dump(mode="json"),
                }
                for chunk in retrieval_context.evidence_chunks
            ],
            "registry": self.registry.model_dump(mode="json"),
            "profile": profile_to_context(self.profile),
            "output_schema": "EpisodeOutlinePlan",
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a short-drama episode planning task. Return only "
                    "JSON matching EpisodeOutlinePlan with exactly 10 "
                    "EpisodeOutline items when enough evidence is available. "
                    "Each outline must include number, opening_hook, "
                    "main_conflict, emotional_payoff, cliffhanger, and "
                    "source_ranges. Use SourceLink objects to show which "
                    "provided novel ranges support each outline. Do not write "
                    "scenes, beats, dialogue, or full script content. Do not "
                    "invent source text or cite evidence outside the provided "
                    "chunks."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ]

    def extra_validate(
        self,
        output: BaseModel,
        retrieval_context: RetrievalContext,
        store: EvidenceStore,
    ) -> list[ValidationFinding]:
        if not isinstance(output, EpisodeOutlinePlan):
            return []

        findings: list[ValidationFinding] = []
        for index, outline in enumerate(output.outlines):
            for finding in lint_outline(
                outline,
                registry=self.registry,
                profile=self.profile,
            ):
                findings.append(
                    ValidationFinding(
                        code=finding.code,
                        severity=finding.severity,
                        message=finding.message,
                        path=_prefix_path(f"outlines[{index}]", finding.path),
                    )
                )
        return findings


def _prefix_path(prefix: str, path: str | None) -> str:
    if path:
        return f"{prefix}.{path}"
    return prefix
