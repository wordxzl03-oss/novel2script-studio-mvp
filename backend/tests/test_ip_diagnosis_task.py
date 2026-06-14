from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import Registry, SourceChapter, SourceNovel


def sample_novel() -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "Mira finds a sealed letter and decides to reopen the case.",
                    "Rowan hides the letter in the archive before dawn.",
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
                {"location_id": "L001", "name": "archive", "aliases": []},
            ],
            "relationship_map": [
                {
                    "from_character_id": "C001",
                    "to_character_id": "C002",
                    "relationship": "Mira suspects Rowan is hiding evidence.",
                }
            ],
        }
    )


def sample_store() -> EvidenceStore:
    store = EvidenceStore()
    store.add_chunks(chunk_novel(sample_novel(), registry=sample_registry()))
    return store


def retrieval_context_for(fixture_case: str, *paragraphs: int) -> RetrievalContext:
    store = sample_store()
    chunks = [store.get(f"CH001:p{paragraph}-{paragraph}") for paragraph in paragraphs]
    return RetrievalContext(
        task_name="ip_diagnosis",
        query=f"diagnose IP adaptation fit: {fixture_case}",
        filters={"fixture_case": fixture_case},
        evidence_chunks=[chunk for chunk in chunks if chunk is not None],
        locked_items={},
        profile_context={},
        project_memory=[],
    )


def test_ip_diagnosis_replay_produces_valid_diagnosis(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("IPDiagnosisTask replay must not call live API")
        ),
    )

    from app.ai.tasks.ip_diagnosis import IPDiagnosisTask

    task = IPDiagnosisTask()
    context = retrieval_context_for("valid", 1)
    messages = task.build_messages(context)

    assert "female_revenge_vertical" in messages[1]["content"]

    result = task.run(context, sample_store())

    assert result.task_run.status == "success"
    assert result.task_run.llm_mode == "replay"
    assert result.task_run.validation_report.passed is True
    assert result.output.recommended_profile_id == "female_revenge_vertical"
    assert result.output.core_conflict_strength.rationale.evidence is not None
    assert result.output.protagonist_desire_clarity.rationale.evidence is not None
    assert result.task_run.usage["total_tokens"] > 0


def test_ip_diagnosis_unknown_profile_id_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.ai.tasks.ip_diagnosis import IPDiagnosisTask

    task = IPDiagnosisTask()
    context = retrieval_context_for("unknown_profile", 1)

    result = task.run(context, sample_store())

    assert result.task_run.status == "failed"
    assert result.task_run.validation_report.passed is False
    assert "unknown_profile_id" in [
        finding.code for finding in result.task_run.validation_report.findings
    ]


def test_ip_diagnosis_fabricated_citation_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.ai.tasks.ip_diagnosis import IPDiagnosisTask

    task = IPDiagnosisTask()
    context = retrieval_context_for("fabricated_citation", 1)

    result = task.run(context, sample_store())

    assert result.task_run.status == "failed"
    assert result.task_run.validation_report.passed is False
    assert "citation_not_in_retrieval" in [
        finding.code for finding in result.task_run.validation_report.findings
    ]
