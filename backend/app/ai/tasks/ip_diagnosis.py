from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.ai.structured_task import StructuredGenerationTask
from app.ai.task import ValidationFinding
from app.profiles.loader import list_profiles
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import IPDiagnosis


class IPDiagnosisTask(StructuredGenerationTask):
    output_model = IPDiagnosis
    temperature = 0.2

    def __init__(self, **kwargs: Any) -> None:
        self._profiles = list_profiles()
        self.profile_ids = [profile.profile_id for profile in self._profiles]
        super().__init__(**kwargs)

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "task": "ip_diagnosis",
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
            "registered_profiles": self._profile_payloads(),
            "output_schema": "IPDiagnosis",
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a short-drama IP diagnosis task. Return only JSON "
                    "matching IPDiagnosis. Use only the provided evidence chunks. "
                    "Every rationale.evidence.source_basis must cite provided "
                    "evidence only. Do not invent source text. Compliance notes "
                    "must describe risks only, not legal conclusions. "
                    "recommended_profile_id must be selected from registered_profiles."
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
        if not isinstance(output, IPDiagnosis):
            return []

        if output.recommended_profile_id in self.profile_ids:
            return []

        return [
            ValidationFinding(
                code="unknown_profile_id",
                severity="error",
                message=(
                    "recommended_profile_id is not registered: "
                    f"{output.recommended_profile_id}"
                ),
                path="recommended_profile_id",
            )
        ]

    def _profile_payloads(self) -> list[dict[str, Any]]:
        return [
            {
                "profile_id": profile.profile_id,
                "display_name": profile.display_name,
                "preferred_conflict_types": profile.preferred_conflict_types,
                "risk_rules": profile.risk_rules,
            }
            for profile in self._profiles
        ]
