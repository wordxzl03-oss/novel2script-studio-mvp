from __future__ import annotations

import json
from typing import Any

from app.ai.structured_task import StructuredGenerationTask
from app.rag.types import RetrievalContext
from app.schema.short_drama import Episode, RetentionPlan


class RetentionPointTask(StructuredGenerationTask):
    output_model = RetentionPlan
    temperature = 0.2

    def __init__(
        self,
        *,
        episode: Episode,
        **kwargs: Any,
    ) -> None:
        self.episode = episode
        super().__init__(**kwargs)

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "task": "retention_points",
            "query": retrieval_context.query,
            "filters": retrieval_context.filters,
            "episode": _episode_payload(self.episode),
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
            "output_schema": "RetentionPlan",
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a short-drama retention planning task. Return only "
                    "RetentionPlan JSON. Mark suggested retention points and "
                    "suggested paywall breakpoints for this episode. Use kind "
                    "values hook, reveal, reversal, cliffhanger for retention "
                    "and paywall for paid breakpoints. Each point must include "
                    "a point_id, kind, description with the recommendation and "
                    "reason, and evidence. Every evidence.source_basis entry "
                    "must cite only provided evidence chunks. Use source_based "
                    "for rewrites and literal_quote only for exact text. The "
                    "wording must stay advisory and must not promise conversion "
                    "or revenue effects. Do not add visual placement fields, "
                    "fidelity scoring, forks, or project persistence."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ]


def attach_retention_points(episode: Episode, plan: RetentionPlan) -> Episode:
    episode.retention_points = list(plan.points)
    return episode


def _episode_payload(episode: Episode) -> dict[str, Any]:
    return {
        "episode_id": episode.episode_id,
        "number": episode.number,
        "title": episode.title,
        "logline": episode.logline,
        "opening_hook": episode.opening_hook,
        "main_conflict": episode.main_conflict,
        "emotional_payoff": episode.emotional_payoff,
        "cliffhanger": episode.cliffhanger,
        "source_ranges": [
            source_link.model_dump(mode="json")
            for source_link in episode.source_ranges
        ],
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "source_links": [
                    source_link.model_dump(mode="json")
                    for source_link in scene.source_links
                ],
                "beats": [
                    {
                        "beat_id": beat.beat_id,
                        "summary": beat.summary,
                        "elements": [
                            element.model_dump(mode="json") for element in beat.elements
                        ],
                    }
                    for beat in scene.beats
                ],
            }
            for scene in episode.scenes
        ],
    }
