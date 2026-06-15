from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.schema.short_drama import (
    EvidenceMeta,
    EvidenceText,
    Registry,
    SourceChapter,
    SourceNovel,
    StoryBible,
)


def sample_novel(*, title: str = "Harbor Case Agent Bible") -> SourceNovel:
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


def locked_text(text: str) -> EvidenceText:
    return EvidenceText(
        text=text,
        evidence=EvidenceMeta(
            source_basis=[],
            confidence=1.0,
            is_inferred=True,
            user_locked=True,
        ),
    )


def existing_bible_with_locked_premise() -> StoryBible:
    return StoryBible(
        premise=locked_text("Locked premise stays."),
        themes=[locked_text("Locked theme stays.")],
    )


def test_story_bible_agent_replay_success_and_indexes(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("StoryBibleAgent replay must not call live API")
        ),
    )

    from app.agents.story_bible_agent import StoryBibleAgent

    novel = sample_novel()
    store = sample_store(novel)
    agent = StoryBibleAgent(store=store)

    run = agent.run(
        project_id="P001",
        source_novel=novel,
        registry=sample_registry(),
    )

    assert run.agent_name == "story_bible_agent"
    assert run.project_id == "P001"
    assert run.target_id == "N001"
    assert run.status == "success"
    assert run.final_output_ref is not None
    assert run.final_output_ref.startswith("story_bible:")
    assert [step.step_name for step in run.steps] == [
        "retrieve_context",
        "run_bible",
        "merge_locked",
        "index_bible",
        "validate",
    ]
    assert [step.status for step in run.steps] == [
        "success",
        "success",
        "success",
        "success",
        "success",
    ]
    task_run = run.steps[1].task_run
    assert task_run is not None
    assert task_run.task_name == "StoryBibleTask"
    assert task_run.status == "success"
    assert task_run.validation_report.passed is True
    assert len(task_run.retrieval_context.evidence_chunks) == 2
    assert store.get("story_bible:premise") is not None
    assert {
        chunk.chunk_id for chunk in store.list_by_tag(event_tag="story_bible")
    } >= {"story_bible:premise", "story_bible:core_hook"}


def test_story_bible_agent_preserves_user_locked_premise(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.agents.story_bible_agent import StoryBibleAgent

    novel = sample_novel(title="Harbor Case Locked Premise")
    store = sample_store(novel)
    agent = StoryBibleAgent(store=store)

    run = agent.run(
        project_id="P001",
        source_novel=novel,
        registry=sample_registry(),
        existing_bible=existing_bible_with_locked_premise(),
    )

    assert run.status == "success"
    premise_chunk = store.get("story_bible:premise")
    assert premise_chunk is not None
    assert premise_chunk.text == "Locked premise stays."
    assert store.get("story_bible:core_hook") is not None
    assert [
        chunk.text for chunk in store.list_by_tag(event_tag="themes")
    ] == ["Locked theme stays.", "Generated theme for unlocked merge."]


def test_story_bible_agent_reports_failure_when_task_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.agents.story_bible_agent import StoryBibleAgent

    novel = sample_novel(title="Harbor Case Missing Bible Evidence")
    agent = StoryBibleAgent(store=sample_store(novel))

    run = agent.run(
        project_id="P001",
        source_novel=novel,
        registry=sample_registry(),
    )

    assert run.status == "failed"
    assert run.final_output_ref is None
    assert [step.status for step in run.steps] == [
        "success",
        "failed",
        "skipped",
        "skipped",
        "failed",
    ]
    task_run = run.steps[1].task_run
    assert task_run is not None
    assert task_run.status == "failed"
    assert "missing_source_basis" in [
        finding.code for finding in task_run.validation_report.findings
    ]
