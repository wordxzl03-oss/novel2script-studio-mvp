from __future__ import annotations

import json
from typing import Any

from app.ai.structured_task import StructuredGenerationTask
from app.llm.client import LLMClient
from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.types import RetrievalContext
from app.schema.short_drama import (
    EvidenceText,
    Registry,
    SourceChapter,
    SourceNovel,
    StrictModel,
)


class MiniOutput(StrictModel):
    summary: EvidenceText


class MiniStructuredTask(StructuredGenerationTask):
    output_model = MiniOutput
    temperature = 0.0

    def build_messages(self, retrieval_context: RetrievalContext) -> list[dict[str, Any]]:
        payload = {
            "query": retrieval_context.query,
            "evidence_chunks": [
                chunk.model_dump(mode="json")
                for chunk in retrieval_context.evidence_chunks
            ],
        }
        return [
            {
                "role": "system",
                "content": "Return only MiniOutput JSON with a summary EvidenceText.",
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ]


def sample_novel() -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title="Harbor Case",
        chapters=[
            SourceChapter(
                chapter_id="CH001",
                title="Letter",
                paragraphs=[
                    "Mira finds a sealed letter.",
                    "Rowan hides the letter in the archive.",
                ],
            )
        ],
    )


def sample_registry() -> Registry:
    return Registry.model_validate(
        {
            "characters": [{"character_id": "C001", "name": "Mira"}],
            "locations": [{"location_id": "L001", "name": "archive"}],
        }
    )


def sample_store() -> EvidenceStore:
    store = EvidenceStore()
    store.add_chunks(chunk_novel(sample_novel(), registry=sample_registry()))
    return store


def retrieval_context_for(*paragraphs: int) -> RetrievalContext:
    store = sample_store()
    chunks = [store.get(f"CH001:p{paragraph}-{paragraph}") for paragraph in paragraphs]
    return RetrievalContext(
        task_name="mini_structured_task",
        query="summarize source evidence",
        filters={},
        evidence_chunks=[chunk for chunk in chunks if chunk is not None],
        locked_items={},
        profile_context={},
        project_memory=[],
    )


def output_content(*, paragraph: int = 1, text: str = "Mira finds the letter.") -> str:
    return json.dumps(
        {
            "summary": {
                "text": text,
                "evidence": {
                    "source_basis": [
                        {
                            "type": "source_based",
                            "source_range": {
                                "chapter_id": "CH001",
                                "start_para": paragraph,
                                "end_para": paragraph,
                            },
                        }
                    ],
                    "confidence": 0.9,
                    "is_inferred": False,
                    "user_locked": False,
                },
            }
        },
        ensure_ascii=False,
    )


def write_recording(
    client: LLMClient,
    *,
    messages: list[dict[str, Any]],
    temperature: float,
    content: str,
) -> None:
    client.recordings_dir.mkdir(parents=True, exist_ok=True)
    path = client.recordings_dir / f"{client.request_key(messages, temperature)}.json"
    path.write_text(
        json.dumps(
            {
                "request": {
                    "messages": messages,
                    "temperature": temperature,
                },
                "response": {
                    "content": content,
                    "usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 7,
                        "total_tokens": 18,
                    },
                },
                "fixture": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def task_with_recordings(tmp_path) -> MiniStructuredTask:
    client = LLMClient(mode="replay", recordings_dir=tmp_path)
    return MiniStructuredTask(llm_client=client)


def test_structured_task_replay_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    task = task_with_recordings(tmp_path)
    context = retrieval_context_for(1)
    messages = task.build_messages(context)
    write_recording(
        task.llm_client,
        messages=messages,
        temperature=task.temperature,
        content=output_content(),
    )

    result = task.run(context, sample_store())

    assert result.output.summary.text == "Mira finds the letter."
    assert result.task_run.task_name == "MiniStructuredTask"
    assert result.task_run.output_schema == "MiniOutput"
    assert result.task_run.llm_mode == "replay"
    assert result.task_run.validation_report.passed is True
    assert result.task_run.status == "success"
    assert result.task_run.usage["total_tokens"] == 18


def test_structured_task_fails_on_fabricated_citation(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    task = task_with_recordings(tmp_path)
    context = retrieval_context_for(1)
    messages = task.build_messages(context)
    write_recording(
        task.llm_client,
        messages=messages,
        temperature=task.temperature,
        content=output_content(paragraph=2, text="Rowan hides the letter."),
    )

    result = task.run(context, sample_store())

    assert result.task_run.status == "failed"
    assert result.task_run.validation_report.passed is False
    assert "citation_not_in_retrieval" in [
        finding.code for finding in result.task_run.validation_report.findings
    ]


def test_structured_task_json_repair_counts_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    task = task_with_recordings(tmp_path)
    context = retrieval_context_for(1)
    messages = task.build_messages(context)
    bad_json = "{not valid json"
    write_recording(
        task.llm_client,
        messages=messages,
        temperature=task.temperature,
        content=bad_json,
    )
    repair_messages = task.build_json_repair_messages(messages, bad_json)
    write_recording(
        task.llm_client,
        messages=repair_messages,
        temperature=task.temperature,
        content=output_content(),
    )

    result = task.run(context, sample_store())

    assert result.output.summary.text == "Mira finds the letter."
    assert result.task_run.validation_report.passed is True
    assert result.task_run.repair_attempts == 1
    assert result.task_run.status == "repaired"
    assert result.task_run.usage["total_tokens"] == 36


def test_structured_task_run_serializes(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    task = task_with_recordings(tmp_path)
    context = retrieval_context_for(1)
    messages = task.build_messages(context)
    write_recording(
        task.llm_client,
        messages=messages,
        temperature=task.temperature,
        content=output_content(),
    )

    result = task.run(context, sample_store())
    serialized = json.loads(result.task_run.model_dump_json())

    assert serialized["task_name"] == "MiniStructuredTask"
    assert serialized["validation_report"]["passed"] is True
    assert serialized["retrieval_context"]["evidence_chunks"]
