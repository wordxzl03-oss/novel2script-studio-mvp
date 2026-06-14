from __future__ import annotations

import json
from typing import Any

from app.ai.structured_task import StructuredGenerationTask
from app.rag.types import RetrievalContext
from app.schema.short_drama import StoryBible


class StoryBibleTask(StructuredGenerationTask):
    output_model = StoryBible
    temperature = 0.2

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "task": "story_bible",
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
            "registry": retrieval_context.profile_context.get("registry", {}),
            "output_schema": "StoryBible",
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a short-drama story bible task. Return only JSON "
                    "matching StoryBible. Use only the provided evidence chunks "
                    "and registry summary. premise, core_hook, and every "
                    "major_reveal evidence.source_basis must cite provided "
                    "evidence only. Do not invent source text. Pure inferred "
                    "items must set evidence.is_inferred=true and may have an "
                    "empty source_basis."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ]
