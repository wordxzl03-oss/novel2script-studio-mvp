from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.ai.structured_task import StructuredGenerationTask
from app.ai.task import ValidationFinding
from app.profiles.loader import ShortDramaProfile, profile_to_context
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import Episode, EpisodeOutline, Registry
from app.validation.short_drama_linter import lint_episode


class EpisodeScriptTask(StructuredGenerationTask):
    output_model = Episode
    temperature = 0.2

    def __init__(
        self,
        *,
        outline: EpisodeOutline,
        registry: Registry,
        profile: ShortDramaProfile,
        **kwargs: Any,
    ) -> None:
        self.outline = outline
        self.registry = registry
        self.profile = profile
        super().__init__(**kwargs)

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "task": "episode_script",
            "query": retrieval_context.query,
            "filters": retrieval_context.filters,
            "outline": self.outline.model_dump(mode="json"),
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
            "output_schema": "Episode",
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a short-drama screenwriter. Return only Episode JSON. "
                    "Turn the provided EpisodeOutline into a filmable Episode with "
                    "scenes, beats, and elements. Use element types action, "
                    "dialogue, performance, sound, transition, and title_card. "
                    "Dialogue must use DialogueElement with speaker_id from the "
                    "provided registry only. Keep opening_hook, main_conflict, "
                    "emotional_payoff, cliffhanger, and source_ranges aligned with "
                    "the outline. Every action and dialogue element must include "
                    "source_links from the provided evidence, or use "
                    "invented_for_adaptation with a reason for new adaptation "
                    "material. literal_quote text must be exact; rewritten source "
                    "material must be source_based. Do not add retention points, "
                    "fidelity scoring, forks, or project persistence."
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
        if not isinstance(output, Episode):
            return []

        return lint_episode(
            output,
            registry=self.registry,
            profile=self.profile,
        )
