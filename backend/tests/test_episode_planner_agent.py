from __future__ import annotations

import pytest

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk, EvidenceMetadata
from app.schema.short_drama import (
    Registry,
    Series,
    SourceChapter,
    SourceLink,
    SourceNovel,
    SourceRange,
)


def sample_novel(*, title: str = "Harbor Case Planner Agent") -> SourceNovel:
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


def sample_store(novel: SourceNovel | None = None) -> EvidenceStore:
    novel = novel or sample_novel()
    store = EvidenceStore()
    store.add_chunks(chunk_novel(novel, registry=sample_registry()))
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


def sample_series(*, title: str = "Harbor Case Planner Agent") -> Series:
    return Series.model_validate(
        {
            "series_id": "SRS001",
            "title": title,
            "episodes": [
                {
                    "episode_id": "E001",
                    "number": 1,
                    "title": "Existing placeholder episode",
                    "logline": "Placeholder used before F10 writes real episodes.",
                    "opening_hook": "Mira finds the sealed letter.",
                    "main_conflict": "Mira must decide whether to reopen the case.",
                    "emotional_payoff": "Mira chooses action over silence.",
                    "cliffhanger": "The archive points to Rowan.",
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
                            "scene_id": "SC001",
                            "title": "Letter at the door",
                            "source_links": [
                                {
                                    "type": "source_based",
                                    "source_range": {
                                        "chapter_id": "CH001",
                                        "start_para": 1,
                                        "end_para": 1,
                                    },
                                }
                            ],
                            "beats": [
                                {
                                    "beat_id": "B001",
                                    "summary": "Mira finds the letter.",
                                    "elements": [
                                        {
                                            "element_id": "EL001",
                                            "type": "action",
                                            "text": "Mira picks up the sealed letter.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def load_test_profile():
    from app.profiles.loader import load_profile

    return load_profile("female_revenge_vertical")


def planner_agent():
    from app.agents.episode_planner_agent import EpisodePlannerAgent

    return EpisodePlannerAgent(
        store=sample_store(),
        registry=sample_registry(),
        profile=load_test_profile(),
    )


def test_planner_agent_replay_success_fills_outlines(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("EpisodePlannerAgent replay must not call live API")
        ),
    )

    series = sample_series()
    run = planner_agent().run(project_id="P001", series=series)

    assert run.agent_name == "episode_planner_agent"
    assert run.project_id == "P001"
    assert run.target_id == "SRS001"
    assert run.status == "success"
    assert run.final_output_ref is not None
    assert run.final_output_ref.startswith("episode_outline_plan:")
    assert [step.step_name for step in run.steps] == [
        "retrieve_context",
        "run_planner",
        "store_outlines",
        "validate",
    ]
    assert [step.status for step in run.steps] == [
        "success",
        "success",
        "success",
        "success",
    ]
    task_run = run.steps[1].task_run
    assert task_run is not None
    assert task_run.task_name == "EpisodePlannerTask"
    assert task_run.status == "success"
    assert task_run.validation_report.passed is True
    assert task_run.llm_mode == "replay"
    assert len(series.outlines) == 10
    assert series.outlines[0].source_ranges[0].source_range is not None


def test_planner_agent_reports_failure_when_task_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    series = sample_series(title="Harbor Case Planner Agent Failure")
    run = planner_agent().run(project_id="P001", series=series)

    assert run.status == "failed"
    assert run.final_output_ref is None
    assert [step.status for step in run.steps] == [
        "success",
        "failed",
        "skipped",
        "failed",
    ]
    assert series.outlines == []
    task_run = run.steps[1].task_run
    assert task_run is not None
    assert task_run.status == "failed"
    assert "F2_SOURCE_UNRESOLVED" in [
        finding.code for finding in task_run.validation_report.findings
    ]


def test_planner_agent_validates_step_order():
    agent = planner_agent()

    assert agent.allowed_steps == [
        "retrieve_context",
        "run_planner",
        "store_outlines",
        "validate",
    ]
    agent.validate_step_order(
        ["retrieve_context", "run_planner", "store_outlines", "validate"]
    )
    with pytest.raises(ValueError, match="unknown_step"):
        agent.validate_step_order(["retrieve_context", "unknown_step"])
