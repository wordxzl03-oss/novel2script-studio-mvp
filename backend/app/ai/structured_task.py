from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError

from app.ai.task import (
    AITask,
    AITaskResult,
    AITaskRun,
    ValidationFinding,
    ValidationReport,
)
from app.llm.client import LLMClient
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.validation.pipeline_step import run_source_validation_step


class StructuredOutputJSONError(ValueError):
    """Raised when an LLM response cannot be parsed as a JSON payload."""


class StructuredGenerationTask(AITask):
    """Base class for business tasks that generate one structured Pydantic model."""

    output_model: ClassVar[type[BaseModel]]
    temperature: ClassVar[float] = 0.2
    max_json_repair_attempts: int = 1
    max_schema_repair_attempts: int = 1

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        mode: str | None = None,
        recordings_dir: str | None = None,
        max_json_repair_attempts: int | None = None,
        max_schema_repair_attempts: int | None = None,
    ) -> None:
        output_model = getattr(self, "output_model", None)
        if output_model is None:
            raise TypeError("StructuredGenerationTask subclasses must define output_model")

        super().__init__(
            task_name=self.__class__.__name__,
            input_schema_name="RetrievalContext",
            output_schema_name=output_model.__name__,
        )
        self.llm_client = llm_client or LLMClient(mode=mode, recordings_dir=recordings_dir)
        if max_json_repair_attempts is not None:
            self.max_json_repair_attempts = max_json_repair_attempts
        if max_schema_repair_attempts is not None:
            self.max_schema_repair_attempts = max_schema_repair_attempts

    def parse_output(self, raw_output: Any) -> BaseModel:
        payload = parse_json_payload(raw_output)
        return self.output_model.model_validate(payload)

    def build_json_repair_messages(
        self, messages: list[dict[str, Any]], raw_output: Any
    ) -> list[dict[str, Any]]:
        return messages + [
            {"role": "assistant", "content": str(raw_output)},
            {
                "role": "user",
                "content": (
                    "The previous assistant output was not valid JSON. "
                    "Return only valid JSON for the requested schema."
                ),
            },
        ]

    def build_schema_repair_messages(
        self,
        messages: list[dict[str, Any]],
        raw_output: Any,
        validation_error: str,
    ) -> list[dict[str, Any]]:
        return messages + [
            {"role": "assistant", "content": str(raw_output)},
            {
                "role": "user",
                "content": (
                    "The previous assistant output did not match the target schema. "
                    f"Schema error: {validation_error}. "
                    "Return only corrected JSON for the requested schema."
                ),
            },
        ]

    def validate_output(
        self,
        output: BaseModel,
        retrieval_context: RetrievalContext,
        store: EvidenceStore,
    ) -> ValidationReport:
        return self._validate_output_with_updates(output, retrieval_context, store)[1]

    def extra_validate(
        self,
        output: BaseModel,
        retrieval_context: RetrievalContext,
        store: EvidenceStore,
    ) -> list[ValidationFinding]:
        return []

    def run(self, retrieval_context: RetrievalContext, store: EvidenceStore) -> AITaskResult:
        messages = self.build_messages(retrieval_context)
        usage: dict[str, int] = {}
        repair_attempts = 0

        raw_output = self._chat(messages, usage)
        output, raw_output, repairs, failure = self._parse_with_repairs(
            messages=messages,
            raw_output=raw_output,
            usage=usage,
        )
        repair_attempts += repairs
        if failure is not None:
            return self._result(
                output=None,
                retrieval_context=retrieval_context,
                validation_report=ValidationReport(passed=False, findings=[failure]),
                repair_attempts=repair_attempts,
                usage=usage,
                status="failed",
                messages=messages,
            )

        output, report = self._validate_output_with_updates(
            output,
            retrieval_context,
            store,
        )
        status = _status_for(report, repair_attempts)

        return self._result(
            output=output,
            retrieval_context=retrieval_context,
            validation_report=report,
            repair_attempts=repair_attempts,
            usage=usage,
            status=status,
            messages=messages,
        )

    def _parse_with_repairs(
        self,
        *,
        messages: list[dict[str, Any]],
        raw_output: Any,
        usage: dict[str, int],
    ) -> tuple[BaseModel | None, Any, int, ValidationFinding | None]:
        repair_attempts = 0

        last_json_error: Exception | None = None
        try:
            return self.parse_output(raw_output), raw_output, repair_attempts, None
        except StructuredOutputJSONError as exc:
            last_json_error = exc
        except ValidationError as exc:
            return self._repair_schema(messages, raw_output, str(exc), usage)

        for _ in range(self.max_json_repair_attempts):
            repair_attempts += 1
            repair_messages = self.build_json_repair_messages(messages, raw_output)
            raw_output = self._chat(repair_messages, usage)
            try:
                return self.parse_output(raw_output), raw_output, repair_attempts, None
            except StructuredOutputJSONError as exc:
                last_json_error = exc
            except ValidationError as exc:
                schema_output, raw_output, schema_repairs, failure = self._repair_schema(
                    messages,
                    raw_output,
                    str(exc),
                    usage,
                )
                return schema_output, raw_output, repair_attempts + schema_repairs, failure

        return (
            None,
            raw_output,
            repair_attempts,
            _finding(
                code="json_parse_error",
                message=f"LLM output could not be parsed as JSON: {last_json_error}",
            ),
        )

    def _repair_schema(
        self,
        messages: list[dict[str, Any]],
        raw_output: Any,
        validation_error: str,
        usage: dict[str, int],
    ) -> tuple[BaseModel | None, Any, int, ValidationFinding | None]:
        repair_attempts = 0
        last_error = validation_error

        for _ in range(self.max_schema_repair_attempts):
            repair_attempts += 1
            repair_messages = self.build_schema_repair_messages(
                messages,
                raw_output,
                last_error,
            )
            raw_output = self._chat(repair_messages, usage)
            try:
                return self.parse_output(raw_output), raw_output, repair_attempts, None
            except StructuredOutputJSONError as exc:
                return (
                    None,
                    raw_output,
                    repair_attempts,
                    _finding(
                        code="json_parse_error",
                        message=f"Schema repair output was not valid JSON: {exc}",
                    ),
                )
            except ValidationError as exc:
                last_error = str(exc)

        return (
            None,
            raw_output,
            repair_attempts,
            _finding(
                code="schema_validation_error",
                message=f"LLM output did not match schema: {last_error}",
            ),
        )

    def _validate_output_with_updates(
        self,
        output: BaseModel,
        retrieval_context: RetrievalContext,
        store: EvidenceStore,
    ) -> tuple[BaseModel, ValidationReport]:
        source_result = run_source_validation_step(output, retrieval_context, store)
        findings = list(source_result.validation_report.findings)
        findings.extend(
            self.extra_validate(source_result.output, retrieval_context, store)
        )
        report = ValidationReport(
            passed=not any(finding.severity == "error" for finding in findings),
            findings=findings,
        )
        return source_result.output, report

    def _chat(self, messages: list[dict[str, Any]], usage: dict[str, int]) -> str:
        before = {
            "prompt_tokens": self.llm_client.usage.prompt_tokens,
            "completion_tokens": self.llm_client.usage.completion_tokens,
            "calls": self.llm_client.usage.calls,
        }
        content = self.llm_client.chat(messages, temperature=self.temperature)
        if self.llm_client.mode == "replay":
            call_usage = self._replay_usage(messages)
        else:
            call_usage = {
                "prompt_tokens": self.llm_client.usage.prompt_tokens
                - before["prompt_tokens"],
                "completion_tokens": self.llm_client.usage.completion_tokens
                - before["completion_tokens"],
                "calls": self.llm_client.usage.calls - before["calls"],
            }
            call_usage["total_tokens"] = (
                call_usage["prompt_tokens"] + call_usage["completion_tokens"]
            )

        _add_usage(usage, call_usage)
        return content

    def _replay_usage(self, messages: list[dict[str, Any]]) -> dict[str, int]:
        key = self.llm_client.request_key(messages, self.temperature)
        path = self.llm_client.recordings_dir / f"{key}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("fixture") is not True:
            raise ValueError(f"Replay recording must be marked fixture=true: {path}")

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
        usage["calls"] = 1
        return usage

    def _result(
        self,
        *,
        output: Any,
        retrieval_context: RetrievalContext,
        validation_report: ValidationReport,
        repair_attempts: int,
        usage: dict[str, int],
        status: str,
        messages: list[dict[str, Any]],
    ) -> AITaskResult:
        task_run = AITaskRun(
            task_id=f"{self.task_name}:{self.llm_client.request_key(messages, self.temperature)}",
            task_name=self.task_name,
            input_schema=self.input_schema_name,
            output_schema=self.output_schema_name,
            retrieval_context=retrieval_context,
            llm_mode=self.llm_client.mode,
            validation_report=validation_report,
            repair_attempts=repair_attempts,
            usage=usage,
            status=status,
            created_at=datetime.now(UTC),
        )
        return AITaskResult(output=output, task_run=task_run)


def parse_json_payload(raw_output: Any) -> Any:
    if isinstance(raw_output, str):
        try:
            return json.loads(_strip_code_fence(raw_output))
        except json.JSONDecodeError as exc:
            raise StructuredOutputJSONError(str(exc)) from exc

    if isinstance(raw_output, dict):
        return raw_output

    raise StructuredOutputJSONError(f"Unsupported raw output type: {type(raw_output).__name__}")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _finding(*, code: str, message: str) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity="error",
        message=message,
        path=None,
    )


def _status_for(report: ValidationReport, repair_attempts: int) -> str:
    if not report.passed:
        return "failed"
    if repair_attempts:
        return "repaired"
    return "success"


def _add_usage(total: dict[str, int], call_usage: dict[str, int]) -> None:
    for key, value in call_usage.items():
        if isinstance(value, int) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value
