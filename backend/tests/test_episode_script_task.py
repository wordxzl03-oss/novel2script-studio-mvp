from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import EvidenceChunk, EvidenceMetadata, RetrievalContext
from app.schema.short_drama import (
    EpisodeOutline,
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
            chapter_id="CH001",
            para_range=(1, 3),
            character_ids=["C001", "C002"],
            location_ids=["L001", "L002"],
            event_tags=["story_bible"],
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


def load_test_profile():
    from app.profiles.loader import load_profile

    return load_profile("female_revenge_vertical")


def retrieval_context_for(fixture_case: str) -> RetrievalContext:
    store = sample_store()
    chunks = [
        store.get("CH001:p1-1"),
        store.get("CH001:p2-2"),
        store.get("CH001:p3-3"),
        story_bible_chunk(),
    ]
    return RetrievalContext(
        task_name="episode_script",
        query=f"write episode 1 script: {fixture_case}",
        filters={"fixture_case": fixture_case, "episode_number": 1},
        evidence_chunks=[chunk for chunk in chunks if chunk is not None],
        locked_items={},
        profile_context={},
        project_memory=[],
    )


def script_task():
    from app.ai.tasks.episode_script import EpisodeScriptTask

    return EpisodeScriptTask(
        outline=sample_outline(),
        registry=sample_registry(),
        profile=load_test_profile(),
    )


def test_script_replay_produces_valid_episode(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("EpisodeScriptTask replay must not call live API")
        ),
    )

    task = script_task()
    context = retrieval_context_for("valid")
    messages = task.build_messages(context)

    assert "Episode JSON" in messages[0]["content"]
    assert "DialogueElement" in messages[0]["content"]
    assert "The Letter" in messages[1]["content"]
    assert "story_bible:premise" in messages[1]["content"]

    result = task.run(context, sample_store())

    assert result.task_run.status == "success"
    assert result.task_run.llm_mode == "replay"
    assert result.task_run.validation_report.passed is True
    assert result.output.number == sample_outline().number
    assert result.output.opening_hook == sample_outline().opening_hook
    assert result.output.source_ranges == sample_outline().source_ranges
    assert result.output.scenes[0].beats[0].elements

    action = result.output.scenes[0].beats[0].elements[0]
    dialogue = result.output.scenes[0].beats[0].elements[1]
    assert action.type == "action"
    assert action.source_links
    assert dialogue.type == "dialogue"
    assert dialogue.speaker_id in {"C001", "C002"}
    assert dialogue.source_links
    assert result.task_run.usage["total_tokens"] > 0


def test_script_unregistered_speaker_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    result = script_task().run(
        retrieval_context_for("unregistered_speaker"),
        sample_store(),
    )

    assert result.task_run.status == "failed"
    assert result.task_run.validation_report.passed is False
    findings = result.task_run.validation_report.findings
    assert "unregistered_character" in [finding.code for finding in findings]
    assert any(
        finding.path == "scenes[0].beats[0].elements[1].speaker_id"
        for finding in findings
    )


def test_script_fabricated_citation_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    result = script_task().run(
        retrieval_context_for("fabricated_citation"),
        sample_store(),
    )

    assert result.task_run.status == "failed"
    assert result.task_run.validation_report.passed is False
    findings = result.task_run.validation_report.findings
    assert "F2_SOURCE_UNRESOLVED" in [finding.code for finding in findings]
    assert any(
        finding.path
        == "output.scenes[0].beats[0].elements[0].source_links[0].source_range"
        for finding in findings
    )
