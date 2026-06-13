import json

import pytest

from app.ai.task import AITaskResult, AITaskRun, ValidationReport
from app.llm.client import RecordingMissingError
from app.rag.types import RetrievalContext


def run_smoke_task(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("LLM_MODE", raising=False)

    from app.ai.smoke_task import SmokeRewriteTask

    return SmokeRewriteTask().run()


def test_smoke_task_runs_in_replay_mode(monkeypatch):
    result = run_smoke_task(monkeypatch)

    assert result.output.rewritten_text == "她抬头看向雨幕:这一次,我不退了。"
    assert result.output.source_basis == []
    assert result.output.is_inferred is True
    assert result.task_run.llm_mode == "replay"


def test_smoke_task_returns_task_run(monkeypatch):
    result = run_smoke_task(monkeypatch)

    assert isinstance(result, AITaskResult)
    assert isinstance(result.task_run, AITaskRun)
    assert result.task_run.task_name == "SmokeRewriteTask"
    assert result.task_run.status == "success"


def test_smoke_task_task_run_has_retrieval_context_and_validation_report(monkeypatch):
    result = run_smoke_task(monkeypatch)

    assert isinstance(result.task_run.retrieval_context, RetrievalContext)
    assert result.task_run.retrieval_context.evidence_chunks
    assert isinstance(result.task_run.validation_report, ValidationReport)
    assert result.task_run.validation_report.passed is True
    assert result.task_run.usage["prompt_tokens"] > 0
    assert result.task_run.usage["completion_tokens"] > 0


def test_smoke_task_does_not_call_live_api(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("live API should not be called in replay smoke task")

    monkeypatch.setattr("app.llm.client.httpx.post", fail_if_called)

    result = run_smoke_task(monkeypatch)

    assert result.task_run.llm_mode == "replay"


def test_smoke_task_replay_recording_is_fixture(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.ai.smoke_task import SmokeRewriteTask

    task = SmokeRewriteTask()
    recording = json.loads(task.recording_path().read_text(encoding="utf-8"))

    assert recording["fixture"] is True
    assert recording["response"]["usage"]["total_tokens"] > 0


def test_smoke_task_missing_replay_recording_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "1")

    from app.ai.smoke_task import SmokeRewriteTask

    task = SmokeRewriteTask(recordings_dir=tmp_path)

    with pytest.raises(RecordingMissingError):
        task.run()
