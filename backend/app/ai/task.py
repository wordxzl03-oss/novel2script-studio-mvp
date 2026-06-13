from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.rag.types import RetrievalContext

FindingSeverity = Literal["error", "warning", "info"]
LLMMode = Literal["live", "record", "replay"]
AITaskStatus = Literal["success", "failed", "repaired"]


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationFinding(StrictAIModel):
    code: str = Field(min_length=1)
    severity: FindingSeverity
    message: str = Field(min_length=1)
    path: str | None = None


class ValidationReport(StrictAIModel):
    passed: bool
    findings: list[ValidationFinding] = Field(default_factory=list)


class AITaskRun(StrictAIModel):
    task_id: str = Field(min_length=1)
    task_name: str = Field(min_length=1)
    input_schema: str = Field(min_length=1)
    output_schema: str = Field(min_length=1)
    retrieval_context: RetrievalContext
    llm_mode: LLMMode
    validation_report: ValidationReport
    repair_attempts: int = Field(ge=0)
    usage: dict[str, int] = Field(default_factory=dict)
    status: AITaskStatus
    created_at: datetime


class AITaskResult(StrictAIModel):
    output: Any
    task_run: AITaskRun


class AITask:
    task_name: str
    input_schema_name: str
    output_schema_name: str

    def __init__(
        self,
        *,
        task_name: str,
        input_schema_name: str,
        output_schema_name: str,
    ) -> None:
        self.task_name = task_name
        self.input_schema_name = input_schema_name
        self.output_schema_name = output_schema_name

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        raise NotImplementedError("AITask.build_messages must be implemented by a concrete task")

    def parse_output(self, raw_output: Any) -> Any:
        raise NotImplementedError("AITask.parse_output must be implemented by a concrete task")

    def validate_output(self, output: Any) -> ValidationReport:
        raise NotImplementedError("AITask.validate_output must be implemented by a concrete task")

    def run(self, retrieval_context: RetrievalContext) -> AITaskResult:
        raise NotImplementedError("AITask.run requires an orchestrator or concrete task implementation")
