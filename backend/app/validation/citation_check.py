from __future__ import annotations

from app.ai.task import ValidationFinding
from app.rag.types import EvidenceChunk, RetrievalContext
from app.schema.short_drama import EvidenceMeta, SourceLink, SourceRange


def check_citation_consistency(
    evidence: EvidenceMeta, context: RetrievalContext
) -> list[ValidationFinding]:
    if not evidence.source_basis:
        if evidence.is_inferred:
            return []
        return [
            _finding(
                code="missing_source_basis",
                message="evidence has no source_basis and is not marked inferred",
                path="source_basis",
            )
        ]

    findings: list[ValidationFinding] = []
    for index, source_link in enumerate(evidence.source_basis):
        if not _source_link_in_context(source_link, context):
            findings.append(
                _finding(
                    code="citation_not_in_retrieval",
                    message="source_basis citation was not present in RetrievalContext",
                    path=f"source_basis[{index}]",
                )
            )

    return findings


def _source_link_in_context(
    source_link: SourceLink, context: RetrievalContext
) -> bool:
    if source_link.source_range is None:
        return source_link.type == "invented_for_adaptation"

    return _source_range_covered_by_chunks(
        source_link.source_range, context.evidence_chunks
    )


def _source_range_covered_by_chunks(
    source_range: SourceRange, chunks: list[EvidenceChunk]
) -> bool:
    covered_paras: set[int] = set()
    for chunk in chunks:
        if chunk.metadata.chapter_id != source_range.chapter_id:
            continue
        if chunk.metadata.para_range is None:
            continue

        chunk_start, chunk_end = chunk.metadata.para_range
        covered_paras.update(range(chunk_start, chunk_end + 1))

    expected_paras = set(range(source_range.start_para, source_range.end_para + 1))
    return expected_paras.issubset(covered_paras)


def _finding(*, code: str, message: str, path: str) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity="error",
        message=message,
        path=path,
    )
