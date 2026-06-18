from __future__ import annotations

from typing import Any

from app.agents.base import AgentRun, AgentStep, BoundedAgent
from app.ai.tasks.ip_diagnosis import IPDiagnosisTask
from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import EmptyRetrievalError, build_retrieval_context
from app.schema.short_drama import IPDiagnosis, Registry, SourceNovel, SourceRange


class DiagnosisAgent(BoundedAgent):
    allowed_steps = ["retrieve_context", "run_diagnosis", "validate"]

    def __init__(
        self,
        *,
        store: EvidenceStore,
        llm_client: Any | None = None,
        profile_ids: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_name="diagnosis_agent",
            allowed_steps=self.allowed_steps,
        )
        self.store = store
        self.llm_client = llm_client
        self.profile_ids = profile_ids or []

    def run(
        self,
        *,
        project_id: str,
        source_novel: SourceNovel,
        registry: Registry,
    ) -> AgentRun:
        step_order = ["retrieve_context", "run_diagnosis", "validate"]
        self.validate_step_order(step_order)

        steps: list[AgentStep] = []
        try:
            retrieval_context = build_retrieval_context(
                task_name="ip_diagnosis",
                query=f"diagnose IP adaptation fit for {source_novel.title}",
                store=self.store,
                source_ranges=_full_novel_ranges(source_novel),
                filters={
                    "chapter_ids": [
                        chapter.chapter_id for chapter in source_novel.chapters
                    ],
                    "character_ids": [
                        character.character_id for character in registry.characters
                    ],
                },
                profile_context={
                    "registry": registry.model_dump(mode="json"),
                    "profile_ids": self.profile_ids,
                },
            )
        except EmptyRetrievalError as exc:
            steps.extend(
                [
                    AgentStep(
                        step_name="retrieve_context",
                        status="failed",
                        message=str(exc),
                    ),
                    AgentStep(
                        step_name="run_diagnosis",
                        status="skipped",
                        message="retrieval failed",
                    ),
                    AgentStep(
                        step_name="validate",
                        status="skipped",
                        message="diagnosis task did not run",
                    ),
                ]
            )
            return AgentRun(
                agent_name=self.agent_name,
                project_id=project_id,
                target_id=source_novel.novel_id,
                steps=steps,
                final_output_ref=None,
                status="failed",
            )

        steps.append(
            AgentStep(
                step_name="retrieve_context",
                status="success",
                message=(
                    f"retrieved {len(retrieval_context.evidence_chunks)} "
                    "novel evidence chunks"
                ),
            )
        )

        task = IPDiagnosisTask(llm_client=self.llm_client)
        task_result = task.run(retrieval_context, self.store)
        task_passed = task_result.task_run.validation_report.passed
        output = task_result.output if isinstance(task_result.output, IPDiagnosis) else None
        run_step_status = "success" if task_passed else "failed"
        steps.append(
            AgentStep(
                step_name="run_diagnosis",
                task_run=task_result.task_run,
                status=run_step_status,
                message=task_result.task_run.status,
            )
        )

        steps.append(
            AgentStep(
                step_name="validate",
                status="success" if task_passed else "failed",
                message=(
                    "validation passed"
                    if task_passed
                    else "diagnosis validation failed"
                ),
            )
        )

        return AgentRun(
            agent_name=self.agent_name,
            project_id=project_id,
            target_id=source_novel.novel_id,
            steps=steps,
            final_output_ref=(
                f"ip_diagnosis:{task_result.task_run.task_id}"
                if task_passed
                else None
            ),
            output=output if task_passed else None,
            status="success" if task_passed else "failed",
        )


def _full_novel_ranges(source_novel: SourceNovel) -> list[SourceRange]:
    return [
        SourceRange(
            chapter_id=chapter.chapter_id,
            start_para=1,
            end_para=len(chapter.paragraphs),
        )
        for chapter in source_novel.chapters
    ]
