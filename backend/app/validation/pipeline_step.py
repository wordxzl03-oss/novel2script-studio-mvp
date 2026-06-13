from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.task import StrictAIModel, ValidationFinding, ValidationReport
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import EvidenceMeta, SourceLink
from app.validation.citation_check import check_citation_consistency
from app.validation.source_validation import validate_source_link

SourceValidationAction = Literal[
    "downgrade_to_source_based",
    "clear_quote",
    "mark_unverified",
]


class SourceValidationChange(StrictAIModel):
    path: str
    action: SourceValidationAction
    before: dict[str, Any]
    after: dict[str, Any]
    finding_code: str | None = None


class SourceValidationStepResult(StrictAIModel):
    output: Any
    validation_report: ValidationReport
    changes: list[SourceValidationChange] = Field(default_factory=list)


def run_source_validation_step(
    output: Any, retrieval_context: RetrievalContext, store: EvidenceStore
) -> SourceValidationStepResult:
    updated_output = deepcopy(output)
    findings: list[ValidationFinding] = []
    changes: list[SourceValidationChange] = []

    _validate_node(
        updated_output,
        path="output",
        retrieval_context=retrieval_context,
        store=store,
        findings=findings,
        changes=changes,
    )

    return SourceValidationStepResult(
        output=updated_output,
        validation_report=ValidationReport(
            passed=not any(finding.severity == "error" for finding in findings),
            findings=findings,
        ),
        changes=changes,
    )


def _validate_node(
    node: Any,
    *,
    path: str,
    retrieval_context: RetrievalContext,
    store: EvidenceStore,
    findings: list[ValidationFinding],
    changes: list[SourceValidationChange],
) -> None:
    if isinstance(node, SourceLink):
        _validate_and_apply_source_link(node, path, store, findings, changes)

    if isinstance(node, EvidenceMeta):
        findings.extend(
            _with_path_prefix(
                check_citation_consistency(node, retrieval_context),
                path,
            )
        )

    if isinstance(node, BaseModel):
        for field_name in type(node).model_fields:
            _validate_node(
                getattr(node, field_name),
                path=f"{path}.{field_name}",
                retrieval_context=retrieval_context,
                store=store,
                findings=findings,
                changes=changes,
            )
        return

    if isinstance(node, dict):
        for key, value in node.items():
            _validate_node(
                value,
                path=f"{path}.{key}",
                retrieval_context=retrieval_context,
                store=store,
                findings=findings,
                changes=changes,
            )
        return

    if isinstance(node, list):
        for index, item in enumerate(node):
            _validate_node(
                item,
                path=f"{path}[{index}]",
                retrieval_context=retrieval_context,
                store=store,
                findings=findings,
                changes=changes,
            )


def _validate_and_apply_source_link(
    source_link: SourceLink,
    path: str,
    store: EvidenceStore,
    findings: list[ValidationFinding],
    changes: list[SourceValidationChange],
) -> None:
    verdict = validate_source_link(source_link, store)
    if verdict.finding is not None:
        findings.append(_with_path_prefix([verdict.finding], path)[0])

    if verdict.suggested_action == "accept":
        return

    before = source_link.model_dump(mode="json")
    if verdict.suggested_action == "downgrade_to_source_based":
        source_link.type = "source_based"
        source_link.quote = None
    elif verdict.suggested_action == "clear_quote":
        source_link.quote = None
        source_link.source_range = None
    elif verdict.suggested_action == "mark_unverified":
        pass

    after = source_link.model_dump(mode="json")
    changes.append(
        SourceValidationChange(
            path=path,
            action=verdict.suggested_action,
            before=before,
            after=after,
            finding_code=verdict.finding.code if verdict.finding is not None else None,
        )
    )


def _with_path_prefix(
    findings: list[ValidationFinding], prefix: str
) -> list[ValidationFinding]:
    prefixed: list[ValidationFinding] = []
    for finding in findings:
        path = prefix
        if finding.path:
            path = f"{prefix}.{finding.path}"
        prefixed.append(
            ValidationFinding(
                code=finding.code,
                severity=finding.severity,
                message=finding.message,
                path=path,
            )
        )
    return prefixed
