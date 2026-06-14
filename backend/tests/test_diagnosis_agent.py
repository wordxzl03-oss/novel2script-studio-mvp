from __future__ import annotations

import pytest

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.schema.short_drama import Registry, SourceChapter, SourceNovel


def sample_novel(*, title: str = "Harbor Case") -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title=title,
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


def sample_store(novel: SourceNovel | None = None) -> EvidenceStore:
    novel = novel or sample_novel()
    store = EvidenceStore()
    store.add_chunks(chunk_novel(novel, registry=sample_registry()))
    return store


def test_diagnosis_agent_replay_success(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("DiagnosisAgent replay must not call live API")
        ),
    )

    from app.agents.diagnosis_agent import DiagnosisAgent

    novel = sample_novel()
    agent = DiagnosisAgent(store=sample_store(novel))

    run = agent.run(
        project_id="P001",
        source_novel=novel,
        registry=sample_registry(),
    )

    assert run.agent_name == "diagnosis_agent"
    assert run.project_id == "P001"
    assert run.target_id == "N001"
    assert run.status == "success"
    assert run.final_output_ref is not None
    assert run.final_output_ref.startswith("ip_diagnosis:")
    assert [step.step_name for step in run.steps] == [
        "retrieve_context",
        "run_diagnosis",
        "validate",
    ]
    assert [step.status for step in run.steps] == ["success", "success", "success"]
    task_run = run.steps[1].task_run
    assert task_run is not None
    assert task_run.task_name == "IPDiagnosisTask"
    assert task_run.status == "success"
    assert task_run.validation_report.passed is True
    assert len(task_run.retrieval_context.evidence_chunks) == 2
    assert task_run.usage["total_tokens"] > 0


def test_diagnosis_agent_reports_failure_when_task_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.agents.diagnosis_agent import DiagnosisAgent

    novel = sample_novel(title="Harbor Case Missing Profile")
    agent = DiagnosisAgent(store=sample_store(novel))

    run = agent.run(
        project_id="P001",
        source_novel=novel,
        registry=sample_registry(),
    )

    assert run.status == "failed"
    assert run.final_output_ref is None
    assert [step.status for step in run.steps] == ["success", "failed", "failed"]
    task_run = run.steps[1].task_run
    assert task_run is not None
    assert task_run.status == "failed"
    assert "unknown_profile_id" in [
        finding.code for finding in task_run.validation_report.findings
    ]


def test_diagnosis_agent_validates_step_order():
    from app.agents.diagnosis_agent import DiagnosisAgent

    agent = DiagnosisAgent(store=sample_store())

    assert agent.allowed_steps == ["retrieve_context", "run_diagnosis", "validate"]
    agent.validate_step_order(["retrieve_context", "run_diagnosis", "validate"])
    with pytest.raises(ValueError, match="unknown_step"):
        agent.validate_step_order(["retrieve_context", "unknown_step"])
