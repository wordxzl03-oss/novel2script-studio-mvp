from __future__ import annotations

from typing import Any

from app.agents.base import AgentRun, AgentStep, BoundedAgent
from app.ai.tasks.story_bible import StoryBibleTask
from app.rag.bible_index import index_story_bible
from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import EmptyRetrievalError, build_retrieval_context
from app.schema.short_drama import (
    EvidenceText,
    Registry,
    SourceNovel,
    SourceRange,
    StoryBible,
)


class StoryBibleAgent(BoundedAgent):
    allowed_steps = [
        "retrieve_context",
        "run_bible",
        "merge_locked",
        "index_bible",
        "validate",
    ]

    def __init__(self, *, store: EvidenceStore, llm_client: Any | None = None) -> None:
        super().__init__(
            agent_name="story_bible_agent",
            allowed_steps=self.allowed_steps,
        )
        self.store = store
        self.llm_client = llm_client

    def run(
        self,
        *,
        project_id: str,
        source_novel: SourceNovel,
        registry: Registry,
        existing_bible: StoryBible | None = None,
    ) -> AgentRun:
        step_order = [
            "retrieve_context",
            "run_bible",
            "merge_locked",
            "index_bible",
            "validate",
        ]
        self.validate_step_order(step_order)

        steps: list[AgentStep] = []
        try:
            retrieval_context = build_retrieval_context(
                task_name="story_bible",
                query=f"build story bible for {source_novel.title}",
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
                profile_context={"registry": registry.model_dump(mode="json")},
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
                        step_name="run_bible",
                        status="skipped",
                        message="retrieval failed",
                    ),
                    AgentStep(
                        step_name="merge_locked",
                        status="skipped",
                        message="story bible task did not run",
                    ),
                    AgentStep(
                        step_name="index_bible",
                        status="skipped",
                        message="story bible task did not run",
                    ),
                    AgentStep(
                        step_name="validate",
                        status="skipped",
                        message="story bible task did not run",
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

        task = StoryBibleTask(llm_client=self.llm_client)
        task_result = task.run(retrieval_context, self.store)
        task_passed = task_result.task_run.validation_report.passed
        steps.append(
            AgentStep(
                step_name="run_bible",
                task_run=task_result.task_run,
                status="success" if task_passed else "failed",
                message=task_result.task_run.status,
            )
        )

        if not task_passed or not isinstance(task_result.output, StoryBible):
            steps.extend(
                [
                    AgentStep(
                        step_name="merge_locked",
                        status="skipped",
                        message="story bible validation failed",
                    ),
                    AgentStep(
                        step_name="index_bible",
                        status="skipped",
                        message="story bible validation failed",
                    ),
                    AgentStep(
                        step_name="validate",
                        status="failed",
                        message="story bible validation failed",
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

        final_bible = _merge_locked_items(task_result.output, existing_bible)
        steps.append(
            AgentStep(
                step_name="merge_locked",
                status="success",
                message="preserved user_locked story bible items",
            )
        )

        chunks = index_story_bible(final_bible, self.store)
        steps.append(
            AgentStep(
                step_name="index_bible",
                status="success",
                message=f"indexed {len(chunks)} story bible chunks",
            )
        )

        steps.append(
            AgentStep(
                step_name="validate",
                status="success",
                message="validation passed",
            )
        )

        return AgentRun(
            agent_name=self.agent_name,
            project_id=project_id,
            target_id=source_novel.novel_id,
            steps=steps,
            final_output_ref=f"story_bible:{task_result.task_run.task_id}",
            output=final_bible,
            status="success",
        )


def _merge_locked_items(
    generated: StoryBible, existing: StoryBible | None
) -> StoryBible:
    if existing is None:
        return generated

    return StoryBible(
        premise=_locked_or_generated(existing.premise, generated.premise),
        core_hook=_locked_or_generated(existing.core_hook, generated.core_hook),
        themes=_merge_locked_list(existing.themes, generated.themes),
        character_arcs=_merge_locked_list(
            existing.character_arcs,
            generated.character_arcs,
        ),
        major_reveals=_merge_locked_list(
            existing.major_reveals,
            generated.major_reveals,
        ),
    )


def _locked_or_generated(
    existing: EvidenceText | None, generated: EvidenceText | None
) -> EvidenceText | None:
    if _is_user_locked(existing):
        return existing
    return generated


def _merge_locked_list(
    existing_items: list[EvidenceText], generated_items: list[EvidenceText]
) -> list[EvidenceText]:
    locked_items = [item for item in existing_items if _is_user_locked(item)]
    return [*locked_items, *generated_items]


def _is_user_locked(item: EvidenceText | None) -> bool:
    return item is not None and item.evidence is not None and item.evidence.user_locked


def _full_novel_ranges(source_novel: SourceNovel) -> list[SourceRange]:
    return [
        SourceRange(
            chapter_id=chapter.chapter_id,
            start_para=1,
            end_para=len(chapter.paragraphs),
        )
        for chapter in source_novel.chapters
    ]
