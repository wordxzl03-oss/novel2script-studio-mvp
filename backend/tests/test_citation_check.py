from app.rag.types import EvidenceChunk, EvidenceMetadata, RetrievalContext
from app.schema.short_drama import EvidenceMeta, SourceLink, SourceRange


def source_range(start: int, end: int | None = None) -> SourceRange:
    return SourceRange(chapter_id="CH001", start_para=start, end_para=end or start)


def evidence_chunk(start: int, end: int | None = None) -> EvidenceChunk:
    resolved_range = source_range(start, end)
    return EvidenceChunk(
        chunk_id=f"CH001:p{resolved_range.start_para}-{resolved_range.end_para}",
        source_type="novel",
        source_ref=SourceLink(type="source_based", source_range=resolved_range),
        text="Retrieved source text.",
        metadata=EvidenceMetadata(
            chapter_id=resolved_range.chapter_id,
            para_range=(resolved_range.start_para, resolved_range.end_para),
            source_hash="sha256:test",
        ),
    )


def retrieval_context(*chunks: EvidenceChunk) -> RetrievalContext:
    return RetrievalContext(
        task_name="episode_writer",
        query="write episode",
        filters={},
        evidence_chunks=list(chunks),
        locked_items={},
        profile_context={},
        project_memory=[],
    )


def test_all_citations_in_retrieval_pass():
    from app.validation.citation_check import check_citation_consistency

    evidence = EvidenceMeta(
        source_basis=[
            SourceLink(type="source_based", source_range=source_range(1, 2)),
            SourceLink(type="literal_quote", source_range=source_range(2), quote="source"),
        ],
        confidence=0.9,
        is_inferred=False,
    )

    findings = check_citation_consistency(evidence, retrieval_context(evidence_chunk(1, 2)))

    assert findings == []


def test_fabricated_citation_flagged():
    from app.validation.citation_check import check_citation_consistency

    evidence = EvidenceMeta(
        source_basis=[SourceLink(type="source_based", source_range=source_range(3))],
        confidence=0.9,
        is_inferred=False,
    )

    findings = check_citation_consistency(evidence, retrieval_context(evidence_chunk(1, 2)))

    assert len(findings) == 1
    assert findings[0].code == "citation_not_in_retrieval"
    assert findings[0].severity == "error"


def test_empty_basis_with_inferred_true_passes():
    from app.validation.citation_check import check_citation_consistency

    evidence = EvidenceMeta(source_basis=[], confidence=0.6, is_inferred=True)

    findings = check_citation_consistency(evidence, retrieval_context(evidence_chunk(1)))

    assert findings == []


def test_empty_basis_without_inferred_flagged():
    from app.validation.citation_check import check_citation_consistency

    evidence = EvidenceMeta(source_basis=[], confidence=0.6, is_inferred=False)

    findings = check_citation_consistency(evidence, retrieval_context(evidence_chunk(1)))

    assert len(findings) == 1
    assert findings[0].severity == "error"
