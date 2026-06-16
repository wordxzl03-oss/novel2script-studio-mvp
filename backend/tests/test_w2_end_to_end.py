from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
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


def test_w2_replay_runs_diagnosis_then_story_bible_without_live_api(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("W2 replay must not call live API")
        ),
    )

    from app.agents.diagnosis_agent import DiagnosisAgent
    from app.agents.story_bible_agent import StoryBibleAgent

    novel = sample_novel()
    registry = sample_registry()
    store = EvidenceStore()
    store.add_chunks(chunk_novel(novel, registry=registry))

    diagnosis_run = DiagnosisAgent(store=store).run(
        project_id="P001",
        source_novel=novel,
        registry=registry,
    )
    bible_run = StoryBibleAgent(store=store).run(
        project_id="P001",
        source_novel=novel,
        registry=registry,
    )

    assert diagnosis_run.status == "success"
    assert bible_run.status == "success"
    assert diagnosis_run.final_output_ref is not None
    assert diagnosis_run.final_output_ref.startswith("ip_diagnosis:")
    assert bible_run.final_output_ref is not None
    assert bible_run.final_output_ref.startswith("story_bible:")

    diagnosis_task_run = diagnosis_run.steps[1].task_run
    bible_task_run = bible_run.steps[1].task_run
    assert diagnosis_task_run is not None
    assert bible_task_run is not None
    assert diagnosis_task_run.llm_mode == "replay"
    assert bible_task_run.llm_mode == "replay"
    assert diagnosis_task_run.usage["calls"] == 1
    assert bible_task_run.usage["calls"] == 1
    assert diagnosis_task_run.usage["total_tokens"] > 0
    assert bible_task_run.usage["total_tokens"] > 0
    assert diagnosis_task_run.validation_report.passed is True
    assert bible_task_run.validation_report.passed is True

    chunks = store.list_by_tag()
    source_types = {chunk.source_type for chunk in chunks}
    assert {"novel", "story_bible"}.issubset(source_types)
    assert [chunk.chunk_id for chunk in chunks if chunk.source_type == "novel"] == [
        "CH001:p1-1",
        "CH001:p2-2",
    ]
    assert {
        chunk.chunk_id for chunk in chunks if chunk.source_type == "story_bible"
    } >= {"story_bible:premise", "story_bible:core_hook"}
