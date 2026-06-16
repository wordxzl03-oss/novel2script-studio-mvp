from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.ai.task import AITaskResult, AITaskRun, ValidationFinding, ValidationReport
from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk, EvidenceMetadata
from app.schema.short_drama import (
    EpisodeOutline,
    Registry,
    Series,
    SourceChapter,
    SourceLink,
    SourceNovel,
    SourceRange,
)


def sample_novel() -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case Writer Agent",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "Mira finds a sealed letter and decides to reopen the case.",
                    "Rowan hides the letter in the archive before dawn.",
                    "Mira confronts Rowan at the pier and records his confession.",
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
                {"location_id": "L002", "name": "pier", "aliases": []},
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
    store.add_chunks([story_bible_chunk()])
    return store


def story_bible_chunk() -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id="story_bible:premise",
        source_type="story_bible",
        source_ref=SourceLink(
            type="source_based",
            source_range=SourceRange(chapter_id="CH001", start_para=1, end_para=3),
        ),
        text=(
            "Mira's investigation escalates from a hidden letter to a public "
            "confrontation with Rowan."
        ),
        metadata=EvidenceMetadata(
            event_tags=["story_bible"],
            chapter_id="CH001",
            para_range=(1, 3),
            character_ids=["C001", "C002"],
            location_ids=["L001", "L002"],
        ),
    )


def sample_outline() -> EpisodeOutline:
    return EpisodeOutline(
        number=1,
        title="The Letter",
        logline="Mira reopens the case after finding a sealed letter.",
        opening_hook="Mira finds a sealed letter hidden under her door.",
        main_conflict="Mira must confront Rowan over the hidden archive letter.",
        emotional_payoff="Mira chooses action instead of silence.",
        cliffhanger="The letter points to Rowan's archive trail.",
        source_ranges=[
            SourceLink(
                type="source_based",
                source_range=SourceRange(chapter_id="CH001", start_para=1, end_para=3),
            )
        ],
    )


def sample_series(*, outline_count: int = 4) -> Series:
    return Series.model_validate(
        {
            "series_id": "SRS001",
            "title": "Harbor Case Writer Agent",
            "episodes": [
                {
                    "episode_id": "E000",
                    "number": 1,
                    "title": "Placeholder",
                    "logline": "Placeholder episode before F10 script writing.",
                    "opening_hook": "Placeholder hook.",
                    "main_conflict": "Placeholder conflict.",
                    "emotional_payoff": "Placeholder payoff.",
                    "cliffhanger": "Placeholder cliffhanger.",
                    "source_ranges": [
                        {
                            "type": "source_based",
                            "source_range": {
                                "chapter_id": "CH001",
                                "start_para": 1,
                                "end_para": 1,
                            },
                        }
                    ],
                    "scenes": [
                        {
                            "scene_id": "SC000",
                            "beats": [
                                {
                                    "beat_id": "B000",
                                    "elements": [
                                        {
                                            "element_id": "EL000",
                                            "type": "action",
                                            "text": "Placeholder action.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
            "outlines": [sample_outline().model_dump(mode="json")] * outline_count,
        }
    )


def load_test_profile():
    from app.profiles.loader import load_profile

    return load_profile("female_revenge_vertical")


def writer_agent():
    from app.agents.episode_writer_agent import EpisodeWriterAgent

    return EpisodeWriterAgent(
        store=sample_store(),
        registry=sample_registry(),
        profile=load_test_profile(),
    )


def test_writer_agent_replay_writes_first_three_episodes(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("EpisodeWriterAgent replay must not call live API")
        ),
    )

    series = sample_series(outline_count=4)
    run = writer_agent().run(project_id="P001", series=series)

    assert run.agent_name == "episode_writer_agent"
    assert run.project_id == "P001"
    assert run.target_id == "SRS001"
    assert run.status == "success"
    assert run.final_output_ref == "series:SRS001:episodes:3"
    assert [step.step_name for step in run.steps] == [
        "select_outline",
        "retrieve_context",
        "run_script",
        "store_episode",
        "select_outline",
        "retrieve_context",
        "run_script",
        "store_episode",
        "select_outline",
        "retrieve_context",
        "run_script",
        "store_episode",
        "validate",
    ]
    assert all(step.status == "success" for step in run.steps)
    task_runs = [
        step.task_run for step in run.steps if step.step_name == "run_script"
    ]
    assert len(task_runs) == 3
    assert all(task_run is not None for task_run in task_runs)
    assert all(task_run.llm_mode == "replay" for task_run in task_runs if task_run)
    assert len(series.episodes) == 3
    assert all(episode.scenes[0].beats[0].elements for episode in series.episodes)
    assert all(
        element.source_links
        for episode in series.episodes
        for scene in episode.scenes
        for beat in scene.beats
        for element in beat.elements
        if element.type in {"action", "dialogue"}
    )


def test_writer_agent_partial_when_one_episode_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.ai.tasks.episode_script import EpisodeScriptTask

    original_run = EpisodeScriptTask.run
    call_count = 0

    def flaky_run(self, retrieval_context, store):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            finding = ValidationFinding(
                code="fixture_failure",
                severity="error",
                message="script task failed for this episode",
                path=None,
            )
            return AITaskResult(
                output=None,
                task_run=AITaskRun(
                    task_id="EpisodeScriptTask:fixture_failure",
                    task_name="EpisodeScriptTask",
                    input_schema="RetrievalContext",
                    output_schema="Episode",
                    retrieval_context=retrieval_context,
                    llm_mode="replay",
                    validation_report=ValidationReport(
                        passed=False,
                        findings=[finding],
                    ),
                    repair_attempts=0,
                    usage={"calls": 1},
                    status="failed",
                    created_at=datetime.now(UTC),
                ),
            )

        return original_run(self, retrieval_context, store)

    monkeypatch.setattr(EpisodeScriptTask, "run", flaky_run)

    series = sample_series(outline_count=3)
    run = writer_agent().run(project_id="P001", series=series)

    assert run.status == "partial"
    assert run.final_output_ref == "series:SRS001:episodes:2"
    assert len(series.episodes) == 2
    run_script_steps = [
        step for step in run.steps if step.step_name == "run_script"
    ]
    store_episode_steps = [
        step for step in run.steps if step.step_name == "store_episode"
    ]
    assert [step.status for step in run_script_steps] == [
        "success",
        "failed",
        "success",
    ]
    assert [step.status for step in store_episode_steps] == [
        "success",
        "skipped",
        "success",
    ]
    assert run.steps[-1].step_name == "validate"
    assert run.steps[-1].status == "failed"


def test_writer_agent_validates_step_order():
    agent = writer_agent()

    assert agent.allowed_steps == [
        "select_outline",
        "retrieve_context",
        "run_script",
        "store_episode",
        "validate",
    ]
    agent.validate_step_order(
        ["select_outline", "retrieve_context", "run_script", "store_episode", "validate"]
    )
    with pytest.raises(ValueError, match="unknown_step"):
        agent.validate_step_order(["select_outline", "unknown_step"])
