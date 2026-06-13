from __future__ import annotations

from typing import Literal

from app.ai.task import ValidationFinding
from app.rag.chunker import normalize_source_text
from app.rag.evidence_store import EvidenceStore
from app.schema.short_drama import SourceLink, SourceRange, StrictModel

SuggestedSourceAction = Literal[
    "accept",
    "downgrade_to_source_based",
    "clear_quote",
    "mark_unverified",
]


class SourceLinkVerdict(StrictModel):
    resolved: bool
    verbatim_ok: bool | None
    suggested_action: SuggestedSourceAction
    finding: ValidationFinding | None


def validate_source_link(link: SourceLink, store: EvidenceStore) -> SourceLinkVerdict:
    if link.type == "literal_quote":
        return _validate_literal_quote(link, store)
    if link.type == "source_based":
        return _validate_source_based(link, store)
    return _validate_invented(link)


def _validate_literal_quote(link: SourceLink, store: EvidenceStore) -> SourceLinkVerdict:
    source_text = _resolve_source_text(link.source_range, store)
    if source_text is None:
        return SourceLinkVerdict(
            resolved=False,
            verbatim_ok=None,
            suggested_action="mark_unverified",
            finding=_finding(
                code="F2_SOURCE_UNRESOLVED",
                message="literal_quote source_range could not be resolved",
                path="source_range",
            ),
        )

    quote = normalize_source_text(link.quote or "")
    if quote and quote in normalize_source_text(source_text):
        return SourceLinkVerdict(
            resolved=True,
            verbatim_ok=True,
            suggested_action="accept",
            finding=None,
        )

    return SourceLinkVerdict(
        resolved=True,
        verbatim_ok=False,
        suggested_action="downgrade_to_source_based",
        finding=_finding(
            code="F2_LITERAL_QUOTE_MISMATCH",
            message="literal_quote quote is not an exact source substring",
            path="quote",
        ),
    )


def _validate_source_based(link: SourceLink, store: EvidenceStore) -> SourceLinkVerdict:
    if _resolve_source_text(link.source_range, store) is not None:
        return SourceLinkVerdict(
            resolved=True,
            verbatim_ok=None,
            suggested_action="accept",
            finding=None,
        )

    return SourceLinkVerdict(
        resolved=False,
        verbatim_ok=None,
        suggested_action="mark_unverified",
        finding=_finding(
            code="F2_SOURCE_UNRESOLVED",
            message="source_based source_range could not be resolved",
            path="source_range",
        ),
    )


def _validate_invented(link: SourceLink) -> SourceLinkVerdict:
    if link.quote or link.source_range is not None:
        return SourceLinkVerdict(
            resolved=False,
            verbatim_ok=None,
            suggested_action="clear_quote",
            finding=_finding(
                code="F2_INVENTED_CLAIMS_SOURCE",
                message="invented_for_adaptation must not claim source text",
                path="source_range",
            ),
        )

    return SourceLinkVerdict(
        resolved=True,
        verbatim_ok=None,
        suggested_action="accept",
        finding=None,
    )


def _resolve_source_text(source_range: SourceRange | None, store: EvidenceStore) -> str | None:
    if source_range is None:
        return None

    chunks = store.get_by_range(
        source_range.chapter_id,
        (source_range.start_para, source_range.end_para),
    )
    if not chunks:
        return None

    covered_paras: set[int] = set()
    for chunk in chunks:
        if chunk.metadata.para_range is None:
            continue
        chunk_start, chunk_end = chunk.metadata.para_range
        covered_paras.update(range(chunk_start, chunk_end + 1))

    expected_paras = set(range(source_range.start_para, source_range.end_para + 1))
    if not expected_paras.issubset(covered_paras):
        return None

    return "\n".join(chunk.text for chunk in chunks)


def _finding(*, code: str, message: str, path: str) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity="error",
        message=message,
        path=path,
    )
