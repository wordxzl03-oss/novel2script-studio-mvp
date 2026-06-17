from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import build_retrieval_context, source_ranges_of
from app.rag.types import EvidenceChunk, EvidenceMetadata
from app.schema.short_drama import (
    Episode,
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
        title="Harbor Case Planner Agent",
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


def sample_store(novel: SourceNovel, registry: Registry) -> EvidenceStore:
    store = EvidenceStore()
    store.add_chunks(chunk_novel(novel, registry=registry))
    store.add_chunks([story_bible_chunk()])
    return store


def story_bible_chunk() -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id="story_bible:premise",
        source_type="story_bible",
        source_ref=source_link(1, 3),
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


def source_link(start_para: int, end_para: int | None = None) -> SourceLink:
    return SourceLink(
        type="source_based",
        source_range=SourceRange(
            chapter_id="CH001",
            start_para=start_para,
            end_para=end_para or start_para,
        ),
    )


def sample_series() -> Series:
    return Series.model_validate(
        {
            "series_id": "SRS001",
            "title": "Harbor Case Planner Agent",
            "episodes": [
                {
                    "episode_id": "E000",
                    "number": 1,
                    "title": "Placeholder",
                    "logline": "Placeholder before W3 replay writes real episodes.",
                    "opening_hook": "Placeholder hook.",
                    "main_conflict": "Placeholder conflict.",
                    "emotional_payoff": "Placeholder payoff.",
                    "cliffhanger": "Placeholder cliffhanger.",
                    "source_ranges": [source_link(1).model_dump(mode="json")],
                    "scenes": [
                        {
                            "scene_id": "SC000",
                            "source_links": [source_link(1).model_dump(mode="json")],
                            "beats": [
                                {
                                    "beat_id": "B000",
                                    "elements": [
                                        {
                                            "element_id": "EL000",
                                            "type": "action",
                                            "text": "Placeholder action.",
                                            "source_links": [
                                                source_link(1).model_dump(mode="json")
                                            ],
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


def retention_context_for(
    *,
    episode: Episode,
    store: EvidenceStore,
    series: Series,
):
    return build_retrieval_context(
        task_name="retention_points",
        query=f"mark retention points for episode {episode.number}",
        store=store,
        source_ranges=source_ranges_of(episode),
        filters={
            "event_tags": ["story_bible"],
            "episode_number": episode.number,
        },
        profile_context={
            "series": {
                "series_id": series.series_id,
                "title": series.title,
            },
            "episode": {
                "episode_id": episode.episode_id,
                "number": episode.number,
            },
        },
    )


def episode_elements_have_source_links(episode: Episode) -> bool:
    return all(
        element.source_links
        for scene in episode.scenes
        for beat in scene.beats
        for element in beat.elements
    )


def test_w3_replay_runs_outline_script_and_retention_chain_without_live_api(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("W3 replay must not call live API")
        ),
    )

    from app.agents.episode_planner_agent import EpisodePlannerAgent
    from app.agents.episode_writer_agent import EpisodeWriterAgent
    from app.ai.tasks.retention_points import (
        RetentionPointTask,
        attach_retention_points,
    )

    novel = sample_novel()
    registry = sample_registry()
    profile = load_test_profile()
    store = sample_store(novel, registry)
    series = sample_series()

    planner_run = EpisodePlannerAgent(
        store=store,
        registry=registry,
        profile=profile,
    ).run(project_id="P001", series=series)
    writer_run = EpisodeWriterAgent(
        store=store,
        registry=registry,
        profile=profile,
    ).run(project_id="P001", series=series, max_episodes=3)

    assert planner_run.status == "success"
    assert writer_run.status == "success"
    assert len(series.outlines) == 10
    assert len(series.episodes) == 3

    planner_task_run = planner_run.steps[1].task_run
    assert planner_task_run is not None
    assert planner_task_run.llm_mode == "replay"
    assert planner_task_run.usage["calls"] == 1
    assert planner_task_run.validation_report.passed is True

    writer_task_runs = [
        step.task_run for step in writer_run.steps if step.step_name == "run_script"
    ]
    assert len(writer_task_runs) == 3
    assert all(task_run is not None for task_run in writer_task_runs)
    assert all(task_run.llm_mode == "replay" for task_run in writer_task_runs if task_run)
    assert all(task_run.usage["calls"] == 1 for task_run in writer_task_runs if task_run)
    assert all(
        task_run.validation_report.passed for task_run in writer_task_runs if task_run
    )

    retention_task_runs = []
    for episode in series.episodes:
        assert episode_elements_have_source_links(episode)

        result = RetentionPointTask(episode=episode).run(
            retention_context_for(episode=episode, store=store, series=series),
            store,
        )
        attach_retention_points(episode, result.output)
        retention_task_runs.append(result.task_run)

    assert all(episode.retention_points for episode in series.episodes)
    assert all(task_run.status == "success" for task_run in retention_task_runs)
    assert all(task_run.llm_mode == "replay" for task_run in retention_task_runs)
    assert all(task_run.usage["calls"] == 1 for task_run in retention_task_runs)
    assert all(task_run.validation_report.passed for task_run in retention_task_runs)
