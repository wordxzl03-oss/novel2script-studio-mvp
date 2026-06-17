from __future__ import annotations

from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import (
    Episode,
    EvidenceMeta,
    Registry,
    RetentionPlan,
    RetentionPoint,
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


def source_link(start_para: int, end_para: int | None = None) -> SourceLink:
    return SourceLink(
        type="source_based",
        source_range=SourceRange(
            chapter_id="CH001",
            start_para=start_para,
            end_para=end_para or start_para,
        ),
    )


def sample_episode() -> Episode:
    return Episode.model_validate(
        {
            "episode_id": "E001",
            "number": 1,
            "title": "The Letter",
            "logline": "Mira reopens the case after finding a sealed letter.",
            "opening_hook": "Mira finds a sealed letter hidden under her door.",
            "main_conflict": "Mira must confront Rowan over the hidden archive letter.",
            "emotional_payoff": "Mira chooses action instead of silence.",
            "cliffhanger": "The letter points to Rowan's archive trail.",
            "source_ranges": [source_link(1, 3).model_dump(mode="json")],
            "scenes": [
                {
                    "scene_id": "SC001",
                    "title": "archive letter confrontation",
                    "source_links": [source_link(1, 3).model_dump(mode="json")],
                    "beats": [
                        {
                            "beat_id": "B001",
                            "summary": "Mira follows the letter trail from the door to Rowan.",
                            "elements": [
                                {
                                    "element_id": "EL001",
                                    "type": "action",
                                    "text": (
                                        "Mira lifts the sealed letter and locks "
                                        "onto the archive stamp."
                                    ),
                                    "source_links": [
                                        source_link(1).model_dump(mode="json")
                                    ],
                                },
                                {
                                    "element_id": "EL002",
                                    "type": "dialogue",
                                    "speaker_id": "C001",
                                    "text": (
                                        "Rowan hid this before dawn, and now I "
                                        "know where he ran."
                                    ),
                                    "source_links": [
                                        source_link(1, 2).model_dump(mode="json")
                                    ],
                                },
                                {
                                    "element_id": "EL003",
                                    "type": "action",
                                    "text": (
                                        "Mira turns on the recorder as Rowan's "
                                        "confession begins at the pier."
                                    ),
                                    "source_links": [
                                        source_link(3).model_dump(mode="json")
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    )


def retrieval_context_for(fixture_case: str, *paragraphs: int) -> RetrievalContext:
    store = sample_store()
    chunks = [store.get(f"CH001:p{paragraph}-{paragraph}") for paragraph in paragraphs]
    return RetrievalContext(
        task_name="retention_points",
        query=f"mark retention points: {fixture_case}",
        filters={"fixture_case": fixture_case, "episode_number": 1},
        evidence_chunks=[chunk for chunk in chunks if chunk is not None],
        locked_items={},
        profile_context={},
        project_memory=[],
    )


def retention_task():
    from app.ai.tasks.retention_points import RetentionPointTask

    return RetentionPointTask(episode=sample_episode())


def test_retention_replay_produces_points(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(
        "app.llm.client.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("RetentionPointTask replay must not call live API")
        ),
    )

    task = retention_task()
    context = retrieval_context_for("valid", 1, 2, 3)
    messages = task.build_messages(context)

    assert "suggested retention" in messages[0]["content"]
    assert "must not promise conversion" in messages[0]["content"]
    assert "Mira finds a sealed letter" in messages[1]["content"]

    result = task.run(context, sample_store())

    assert result.task_run.status == "success"
    assert result.task_run.llm_mode == "replay"
    assert result.task_run.validation_report.passed is True
    assert result.output.points
    assert result.output.points[0].kind in {
        "hook",
        "reveal",
        "reversal",
        "paywall",
        "cliffhanger",
    }
    assert result.output.points[0].evidence is not None
    assert result.output.points[0].evidence.source_basis
    assert result.task_run.usage["total_tokens"] > 0


def test_retention_attach_fills_episode():
    from app.ai.tasks.retention_points import attach_retention_points

    episode = sample_episode()
    plan = RetentionPlan(
        points=[
            RetentionPoint(
                point_id="RP001",
                kind="paywall",
                description=(
                    "Suggested paywall pause after Rowan is tied to the hidden "
                    "archive letter."
                ),
                evidence=EvidenceMeta(
                    source_basis=[source_link(2)],
                    confidence=0.82,
                    is_inferred=False,
                ),
            )
        ]
    )

    returned = attach_retention_points(episode, plan)

    assert returned is episode
    assert episode.retention_points == plan.points


def test_retention_fabricated_citation_fails(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    result = retention_task().run(
        retrieval_context_for("fabricated_citation", 1),
        sample_store(),
    )

    assert result.task_run.status == "failed"
    assert result.task_run.validation_report.passed is False
    findings = result.task_run.validation_report.findings
    assert "citation_not_in_retrieval" in [finding.code for finding in findings]
    assert any(
        finding.path == "output.points[0].evidence.source_basis[0]"
        for finding in findings
    )
