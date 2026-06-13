import json
from datetime import UTC, datetime


def retrieval_context_payload() -> dict:
    return {
        "task_name": "episode_outline",
        "query": "Build episode 1 outline",
        "filters": {"episode": 1},
        "evidence_chunks": [
            {
                "chunk_id": "novel:CH001:1-2",
                "source_type": "novel",
                "source_ref": {
                    "type": "source_based",
                    "source_range": {
                        "chapter_id": "CH001",
                        "start_para": 1,
                        "end_para": 2,
                    },
                },
                "text": "A source novel excerpt used as retrieval evidence.",
                "metadata": {
                    "chapter_id": "CH001",
                    "para_range": (1, 2),
                    "character_ids": ["C001"],
                    "location_ids": ["L001"],
                    "event_tags": ["arrival"],
                },
            }
        ],
        "locked_items": {},
        "profile_context": {"profile_id": "female_revenge_vertical"},
        "project_memory": [],
    }


def task_run_payload() -> dict:
    return {
        "task_id": "TASK001",
        "task_name": "episode_outline",
        "input_schema": "RetrievalContext",
        "output_schema": "ShortDramaProject",
        "retrieval_context": retrieval_context_payload(),
        "llm_mode": "replay",
        "validation_report": {"passed": True, "findings": []},
        "repair_attempts": 0,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "status": "success",
        "created_at": datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
    }


def test_validation_report_passed():
    from app.ai.task import ValidationReport

    report = ValidationReport.model_validate({"passed": True, "findings": []})

    assert report.passed is True
    assert report.findings == []


def test_validation_report_failed_with_finding():
    from app.ai.task import ValidationReport

    report = ValidationReport.model_validate(
        {
            "passed": False,
            "findings": [
                {
                    "code": "E_SCHEMA",
                    "severity": "error",
                    "message": "Output does not match schema.",
                    "path": "$.series.episodes[0]",
                }
            ],
        }
    )

    assert report.passed is False
    assert report.findings[0].code == "E_SCHEMA"
    assert report.findings[0].severity == "error"


def test_ai_task_run_contains_retrieval_context():
    from app.ai.task import AITaskRun
    from app.rag.types import RetrievalContext

    task_run = AITaskRun.model_validate(task_run_payload())

    assert isinstance(task_run.retrieval_context, RetrievalContext)
    assert task_run.retrieval_context.evidence_chunks[0].source_type == "novel"
    assert task_run.llm_mode == "replay"


def test_ai_task_run_serializes_to_json():
    from app.ai.task import AITaskRun

    task_run = AITaskRun.model_validate(task_run_payload())
    dumped = json.loads(task_run.model_dump_json())

    assert dumped["task_id"] == "TASK001"
    assert dumped["retrieval_context"]["evidence_chunks"][0]["source_type"] == "novel"
    assert dumped["validation_report"]["passed"] is True
    assert dumped["created_at"] == "2026-06-13T10:00:00Z"
