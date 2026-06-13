from datetime import UTC, datetime
from pathlib import Path

import pytest


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


def test_agent_run_records_steps():
    from app.agents.base import AgentRun

    agent_run = AgentRun.model_validate(
        {
            "agent_name": "outline_agent",
            "project_id": "P001",
            "target_id": "E01",
            "steps": [
                {"step_name": "collect_evidence", "status": "success"},
                {"step_name": "write_outline", "status": "pending"},
            ],
            "final_output_ref": None,
            "status": "partial",
        }
    )

    assert agent_run.agent_name == "outline_agent"
    assert [step.step_name for step in agent_run.steps] == [
        "collect_evidence",
        "write_outline",
    ]
    assert agent_run.status == "partial"


def test_agent_step_can_hold_task_run():
    from app.agents.base import AgentStep
    from app.ai.task import AITaskRun

    step = AgentStep.model_validate(
        {
            "step_name": "write_outline",
            "task_run": task_run_payload(),
            "status": "success",
            "message": "Outline task completed.",
        }
    )

    assert isinstance(step.task_run, AITaskRun)
    assert step.task_run.task_name == "episode_outline"
    assert step.status == "success"


def test_bounded_agent_rejects_unknown_step():
    from app.agents.base import BoundedAgent

    agent = BoundedAgent(
        agent_name="outline_agent",
        allowed_steps=["collect_evidence", "write_outline"],
    )

    with pytest.raises(ValueError, match="unknown_step"):
        agent.validate_step_order(["collect_evidence", "unknown_step"])


def test_no_export_agent_module_exists():
    assert not Path("backend/app/agents/export_agent.py").exists()
