from copy import deepcopy

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.schema.short_drama import (
    Registry,
    SourceChapter,
    SourceLink,
    SourceNovel,
    SourceRange,
)


def sample_novel() -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "Mira finds a sealed letter.",
                    "Mira meets Rowan at the pier.",
                    "Rowan hides the letter in the archive.",
                ],
            )
        ],
    )


def sample_registry() -> Registry:
    return Registry.model_validate(
        {
            "characters": [
                {"character_id": "C001", "name": "Mira", "aliases": []},
                {"character_id": "C002", "name": "Rowan", "aliases": []},
            ],
            "locations": [
                {"location_id": "L001", "name": "pier", "aliases": []},
                {"location_id": "L002", "name": "archive", "aliases": []},
            ],
        }
    )


def sample_store() -> EvidenceStore:
    store = EvidenceStore()
    store.add_chunks(chunk_novel(sample_novel(), registry=sample_registry()))
    return store


def source_range(start: int, end: int | None = None) -> SourceRange:
    return SourceRange(chapter_id="CH001", start_para=start, end_para=end or start)


def test_literal_quote_exact_match_accepts():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="literal_quote",
        source_range=source_range(1),
        quote="Mira finds a sealed letter.",
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is True
    assert verdict.verbatim_ok is True
    assert verdict.suggested_action == "accept"
    assert verdict.finding is None


def test_literal_quote_single_char_diff_fails_verbatim():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="literal_quote",
        source_range=source_range(1),
        quote="Mira finds a sealed letters.",
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is True
    assert verdict.verbatim_ok is False
    assert verdict.suggested_action == "downgrade_to_source_based"
    assert verdict.finding is not None
    assert verdict.finding.severity == "error"


def test_literal_quote_unresolvable_range_marks_unverified():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="literal_quote",
        source_range=SourceRange(chapter_id="CH001", start_para=9, end_para=9),
        quote="Missing text.",
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is False
    assert verdict.verbatim_ok is None
    assert verdict.suggested_action == "mark_unverified"
    assert verdict.finding is not None
    assert verdict.finding.severity == "error"


def test_source_based_resolvable_accepts():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(type="source_based", source_range=source_range(2, 3))

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is True
    assert verdict.verbatim_ok is None
    assert verdict.suggested_action == "accept"
    assert verdict.finding is None


def test_source_based_unresolvable_marks_unverified():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="source_based",
        source_range=SourceRange(chapter_id="CH002", start_para=1, end_para=1),
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is False
    assert verdict.verbatim_ok is None
    assert verdict.suggested_action == "mark_unverified"
    assert verdict.finding is not None
    assert verdict.finding.severity == "error"


def test_source_based_partially_missing_range_marks_unverified():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="source_based",
        source_range=SourceRange(chapter_id="CH001", start_para=3, end_para=4),
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is False
    assert verdict.suggested_action == "mark_unverified"
    assert verdict.finding is not None


def test_invented_with_fake_quote_flagged():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="invented_for_adaptation",
        reason="Bridge scene for pacing.",
        quote="Mira finds a sealed letter.",
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is False
    assert verdict.verbatim_ok is None
    assert verdict.suggested_action == "clear_quote"
    assert verdict.finding is not None
    assert verdict.finding.severity == "error"


def test_clean_invented_accepts():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="invented_for_adaptation",
        reason="Bridge scene for pacing.",
    )

    verdict = validate_source_link(link, sample_store())

    assert verdict.resolved is True
    assert verdict.verbatim_ok is None
    assert verdict.suggested_action == "accept"
    assert verdict.finding is None


def test_validator_does_not_mutate_link():
    from app.validation.source_validation import validate_source_link

    link = SourceLink(
        type="literal_quote",
        source_range=source_range(1),
        quote="Mira finds a sealed letters.",
    )
    before = deepcopy(link.model_dump())

    validate_source_link(link, sample_store())

    assert link.model_dump() == before
