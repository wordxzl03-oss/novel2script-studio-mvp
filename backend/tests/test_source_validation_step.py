from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import (
    EvidenceMeta,
    Episode,
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


def source_based(start: int, end: int | None = None) -> SourceLink:
    return SourceLink(type="source_based", source_range=source_range(start, end))


def retrieval_context_for(*paragraphs: int) -> RetrievalContext:
    store = sample_store()
    chunks = [store.get(f"CH001:p{paragraph}-{paragraph}") for paragraph in paragraphs]
    return RetrievalContext(
        task_name="episode_writer",
        query="write episode",
        filters={},
        evidence_chunks=[chunk for chunk in chunks if chunk is not None],
        locked_items={},
        profile_context={},
        project_memory=[],
    )


def episode_with_action(
    *,
    source_links: list[SourceLink] | None = None,
    evidence: EvidenceMeta | None = None,
) -> Episode:
    return Episode.model_validate(
        {
            "episode_id": "E001",
            "number": 1,
            "opening_hook": "A letter arrives.",
            "main_conflict": "Mira must choose whom to trust.",
            "emotional_payoff": "Rowan admits the truth.",
            "cliffhanger": "The archive door opens.",
            "source_ranges": [source_based(1).model_dump()],
            "scenes": [
                {
                    "scene_id": "S001",
                    "beats": [
                        {
                            "beat_id": "B001",
                            "elements": [
                                {
                                    "element_id": "A001",
                                    "type": "action",
                                    "text": "Mira reads the letter.",
                                    "source_links": [
                                        link.model_dump()
                                        for link in (source_links or [])
                                    ],
                                    "evidence": evidence.model_dump()
                                    if evidence is not None
                                    else None,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def first_action_source_link(episode: Episode) -> SourceLink:
    return episode.scenes[0].beats[0].elements[0].source_links[0]


def test_step_rejects_fabricated_citation():
    from app.validation.pipeline_step import run_source_validation_step

    output = episode_with_action(
        evidence=EvidenceMeta(
            source_basis=[source_based(3)],
            confidence=0.9,
            is_inferred=False,
        )
    )

    result = run_source_validation_step(
        output,
        retrieval_context_for(1),
        sample_store(),
    )

    assert result.validation_report.passed is False
    assert [finding.code for finding in result.validation_report.findings] == [
        "citation_not_in_retrieval"
    ]
    assert result.changes == []


def test_step_downgrades_bad_literal_quote_and_records_change():
    from app.validation.pipeline_step import run_source_validation_step

    bad_literal = SourceLink(
        type="literal_quote",
        source_range=source_range(1),
        quote="Mira finds a sealed letters.",
    )
    output = episode_with_action(source_links=[bad_literal])

    result = run_source_validation_step(
        output,
        retrieval_context_for(1),
        sample_store(),
    )

    updated_link = first_action_source_link(result.output)
    assert updated_link.type == "source_based"
    assert updated_link.quote is None
    assert first_action_source_link(output).type == "literal_quote"
    assert result.changes[0].action == "downgrade_to_source_based"
    assert result.changes[0].path.endswith("source_links[0]")
    assert result.changes[0].before["type"] == "literal_quote"
    assert result.changes[0].after["type"] == "source_based"
    assert "F2_LITERAL_QUOTE_MISMATCH" in [
        finding.code for finding in result.validation_report.findings
    ]


def test_step_accepts_clean_invented():
    from app.validation.pipeline_step import run_source_validation_step

    output = episode_with_action(
        evidence=EvidenceMeta(
            source_basis=[],
            confidence=0.7,
            is_inferred=True,
        )
    )

    result = run_source_validation_step(
        output,
        retrieval_context_for(1),
        sample_store(),
    )

    assert result.validation_report.passed is True
    assert result.validation_report.findings == []
    assert result.changes == []


def test_step_runs_without_live_llm(monkeypatch):
    from app.llm.client import LLMClient
    from app.validation.pipeline_step import run_source_validation_step

    def fail_on_llm_init(*args: object, **kwargs: object) -> None:
        raise AssertionError("source validation step must not create an LLM client")

    monkeypatch.setattr(LLMClient, "__init__", fail_on_llm_init)

    result = run_source_validation_step(
        episode_with_action(
            evidence=EvidenceMeta(
                source_basis=[],
                confidence=0.7,
                is_inferred=True,
            )
        ),
        retrieval_context_for(1),
        sample_store(),
    )

    assert result.validation_report.passed is True


def test_step_is_callable_as_plain_function_for_validate_output():
    from app.validation.pipeline_step import run_source_validation_step

    def validate_output(output: Episode):
        return run_source_validation_step(
            output,
            retrieval_context_for(1),
            sample_store(),
        ).validation_report

    report = validate_output(
        episode_with_action(
            evidence=EvidenceMeta(
                source_basis=[],
                confidence=0.7,
                is_inferred=True,
            )
        )
    )

    assert report.passed is True
