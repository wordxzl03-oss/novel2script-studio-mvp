import json

import pytest
from pydantic import ValidationError


def novel_chunk_payload() -> dict:
    return {
        "chunk_id": "novel:CH001:1-2",
        "source_type": "novel",
        "source_ref": {
            "type": "source_based",
            "source_range": {"chapter_id": "CH001", "start_para": 1, "end_para": 2},
        },
        "text": "A source novel excerpt used as retrieval evidence.",
        "metadata": {
            "chapter_id": "CH001",
            "para_range": (1, 2),
            "character_ids": ["C001"],
            "location_ids": ["L001"],
            "event_tags": ["arrival"],
            "source_hash": "sha256:novel-001",
        },
    }


def test_evidence_chunk_for_novel_source():
    from app.rag.types import EvidenceChunk

    chunk = EvidenceChunk.model_validate(novel_chunk_payload())

    assert chunk.source_type == "novel"
    assert chunk.source_ref is not None
    assert chunk.source_ref.source_range is not None
    assert chunk.source_ref.source_range.chapter_id == "CH001"
    assert chunk.metadata.para_range == (1, 2)


def test_evidence_chunk_for_script_element():
    from app.rag.types import EvidenceChunk

    chunk = EvidenceChunk.model_validate(
        {
            "chunk_id": "script:E01:SC001:EL001",
            "source_type": "script",
            "source_ref": {
                "type": "invented_for_adaptation",
                "reason": "New visual beat added for short-drama retention.",
            },
            "text": "Hero pauses at the doorway before the reveal.",
            "metadata": {
                "episode_id": "E01",
                "scene_id": "SC001",
                "element_id": "EL001",
                "character_ids": ["C001"],
                "location_ids": ["L001"],
                "event_tags": ["reveal"],
                "emotional_tone": "tense",
            },
        }
    )

    assert chunk.source_type == "script"
    assert chunk.metadata.episode_id == "E01"
    assert chunk.metadata.scene_id == "SC001"
    assert chunk.metadata.element_id == "EL001"
    assert chunk.source_ref is not None
    assert chunk.source_ref.source_range is None


def test_retrieval_context_rejects_empty_evidence_chunks():
    from app.rag.types import RetrievalContext

    with pytest.raises(ValidationError):
        RetrievalContext.model_validate(
            {
                "task_name": "episode_outline",
                "query": "Build episode 1 outline",
                "filters": {"episode": 1},
                "evidence_chunks": [],
                "locked_items": {},
                "profile_context": {},
                "project_memory": [],
            }
        )


def test_retrieval_context_serializes_to_json():
    from app.rag.types import RetrievalContext

    context = RetrievalContext.model_validate(
        {
            "task_name": "episode_outline",
            "query": "Build episode 1 outline",
            "filters": {"episode": 1},
            "evidence_chunks": [novel_chunk_payload()],
            "locked_items": {"episode_id": "E01"},
            "profile_context": {"profile_id": "female_revenge_vertical"},
            "project_memory": [{"key": "tone", "value": "fast"}],
        }
    )

    dumped = json.loads(context.model_dump_json())

    assert dumped["task_name"] == "episode_outline"
    assert dumped["evidence_chunks"][0]["source_type"] == "novel"
    assert dumped["evidence_chunks"][0]["metadata"]["para_range"] == [1, 2]
