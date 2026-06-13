from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from app.ai.task import AITask, AITaskResult, AITaskRun, StrictAIModel, ValidationReport
from app.llm.client import LLMClient
from app.rag.types import RetrievalContext
from app.schema.short_drama import SourceLink

SMOKE_REWRITE_INPUT = {
    "instruction": "把这句话改成更短剧化",
    "text": "她站在雨里,终于意识到自己不能再退让。",
}

SMOKE_TEMPERATURE = 0.0


class SmokeRewriteOutput(StrictAIModel):
    rewritten_text: str = Field(min_length=1)
    source_basis: list[SourceLink] = Field(default_factory=list)
    is_inferred: bool


class SmokeRewriteTask(AITask):
    """W0-only smoke task proving AITask -> LLMClient replay -> AITaskRun."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        recordings_dir: str | Path | None = None,
        mode: str | None = None,
    ) -> None:
        super().__init__(
            task_name="SmokeRewriteTask",
            input_schema_name="SmokeRewriteInput",
            output_schema_name="SmokeRewriteOutput",
        )
        self.llm_client = llm_client or LLMClient(mode=mode, recordings_dir=recordings_dir)

    def build_retrieval_context(self) -> RetrievalContext:
        return RetrievalContext.model_validate(
            {
                "task_name": self.task_name,
                "query": "短剧化改写测试",
                "filters": {"fixture": True},
                "evidence_chunks": [
                    {
                        "chunk_id": "smoke:novel:CH001:1-1",
                        "source_type": "novel",
                        "source_ref": {
                            "type": "source_based",
                            "source_range": {
                                "chapter_id": "CH001",
                                "start_para": 1,
                                "end_para": 1,
                            },
                        },
                        "text": SMOKE_REWRITE_INPUT["text"],
                        "metadata": {
                            "chapter_id": "CH001",
                            "para_range": (1, 1),
                            "character_ids": ["C001"],
                            "location_ids": [],
                            "event_tags": ["turning_point"],
                            "emotional_tone": "defiant",
                            "source_hash": "fixture:smoke-rewrite",
                        },
                    }
                ],
                "locked_items": {},
                "profile_context": {"profile_id": "female_revenge_vertical"},
                "project_memory": [],
            }
        )

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "input": SMOKE_REWRITE_INPUT,
            "retrieval_context": {
                "task_name": retrieval_context.task_name,
                "query": retrieval_context.query,
                "evidence_chunks": [
                    chunk.model_dump(mode="json") for chunk in retrieval_context.evidence_chunks
                ],
                "profile_context": retrieval_context.profile_context,
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a W0 smoke-test rewrite task. Return only JSON with "
                    "keys rewritten_text, source_basis, and is_inferred."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
        ]

    def parse_output(self, raw_output: Any) -> SmokeRewriteOutput:
        if isinstance(raw_output, str):
            raw_output = json.loads(raw_output)
        return SmokeRewriteOutput.model_validate(raw_output)

    def validate_output(self, output: SmokeRewriteOutput) -> ValidationReport:
        return ValidationReport.model_validate({"passed": bool(output.rewritten_text), "findings": []})

    def recording_path(self) -> Path:
        messages = self.build_messages(self.build_retrieval_context())
        key = self.llm_client.request_key(messages, SMOKE_TEMPERATURE)
        return self.llm_client.recordings_dir / f"{key}.json"

    def run(self, retrieval_context: RetrievalContext | None = None) -> AITaskResult:
        retrieval_context = retrieval_context or self.build_retrieval_context()
        messages = self.build_messages(retrieval_context)
        raw_output = self.llm_client.chat(messages, temperature=SMOKE_TEMPERATURE)
        output = self.parse_output(raw_output)
        validation_report = self.validate_output(output)
        usage = self._recording_usage(messages)
        task_run = AITaskRun.model_validate(
            {
                "task_id": f"smoke-rewrite:{self.llm_client.request_key(messages, SMOKE_TEMPERATURE)}",
                "task_name": self.task_name,
                "input_schema": self.input_schema_name,
                "output_schema": self.output_schema_name,
                "retrieval_context": retrieval_context,
                "llm_mode": self.llm_client.mode,
                "validation_report": validation_report,
                "repair_attempts": 0,
                "usage": usage,
                "status": "success" if validation_report.passed else "failed",
                "created_at": datetime.now(UTC),
            }
        )
        return AITaskResult(output=output, task_run=task_run)

    def _recording_usage(self, messages: list[dict[str, Any]]) -> dict[str, int]:
        key = self.llm_client.request_key(messages, SMOKE_TEMPERATURE)
        path = self.llm_client.recordings_dir / f"{key}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("fixture") is not True:
            raise ValueError(f"Smoke replay recording must be marked fixture=true: {path}")

        raw_usage = data.get("response", {}).get("usage", {})
        usage = {
            key: int(value)
            for key, value in raw_usage.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }
        usage.setdefault(
            "total_tokens",
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
        )
        usage["calls"] = self.llm_client.usage.calls
        return usage
