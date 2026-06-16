from __future__ import annotations

from typing import Any

from app.agents.base import AgentRun, AgentStep, BoundedAgent
from app.ai.tasks.episode_planner import EpisodePlannerTask
from app.profiles.loader import ShortDramaProfile
from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import EmptyRetrievalError, build_retrieval_context
from app.schema.short_drama import EpisodeOutlinePlan, Registry, Series, SourceRange


class EpisodePlannerAgent(BoundedAgent):
    allowed_steps = ["retrieve_context", "run_planner", "store_outlines", "validate"]

    def __init__(
        self,
        *,
        store: EvidenceStore,
        registry: Registry,
        profile: ShortDramaProfile,
        llm_client: Any | None = None,
    ) -> None:
        super().__init__(
            agent_name="episode_planner_agent",
            allowed_steps=self.allowed_steps,
        )
        self.store = store
        self.registry = registry
        self.profile = profile
        self.llm_client = llm_client

    def run(self, *, project_id: str, series: Series) -> AgentRun:
        step_order = ["retrieve_context", "run_planner", "store_outlines", "validate"]
        self.validate_step_order(step_order)

        steps: list[AgentStep] = []
        try:
            retrieval_context = build_retrieval_context(
                task_name="episode_planner",
                query=f"plan first 10 short-drama episodes for {series.title}",
                store=self.store,
                source_ranges=_novel_ranges_from_store(self.store),
                filters={"event_tags": ["story_bible"]},
                profile_context={
                    "registry": self.registry.model_dump(mode="json"),
                    "series": {
                        "series_id": series.series_id,
                        "title": series.title,
                    },
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
                        step_name="run_planner",
                        status="skipped",
                        message="retrieval failed",
                    ),
                    AgentStep(
                        step_name="store_outlines",
                        status="skipped",
                        message="planner task did not run",
                    ),
                    AgentStep(
                        step_name="validate",
                        status="skipped",
                        message="planner task did not run",
                    ),
                ]
            )
            return AgentRun(
                agent_name=self.agent_name,
                project_id=project_id,
                target_id=series.series_id,
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
                    "planning evidence chunks"
                ),
            )
        )

        task = EpisodePlannerTask(
            llm_client=self.llm_client,
            registry=self.registry,
            profile=self.profile,
        )
        task_result = task.run(retrieval_context, self.store)
        task_passed = task_result.task_run.validation_report.passed
        steps.append(
            AgentStep(
                step_name="run_planner",
                task_run=task_result.task_run,
                status="success" if task_passed else "failed",
                message=task_result.task_run.status,
            )
        )

        if not task_passed or not isinstance(task_result.output, EpisodeOutlinePlan):
            steps.extend(
                [
                    AgentStep(
                        step_name="store_outlines",
                        status="skipped",
                        message="planner validation failed",
                    ),
                    AgentStep(
                        step_name="validate",
                        status="failed",
                        message="planner validation failed",
                    ),
                ]
            )
            return AgentRun(
                agent_name=self.agent_name,
                project_id=project_id,
                target_id=series.series_id,
                steps=steps,
                final_output_ref=None,
                status="failed",
            )

        series.outlines = task_result.output.outlines
        steps.append(
            AgentStep(
                step_name="store_outlines",
                status="success",
                message=f"stored {len(series.outlines)} episode outlines",
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
            target_id=series.series_id,
            steps=steps,
            final_output_ref=f"episode_outline_plan:{task_result.task_run.task_id}",
            status="success",
        )


def _novel_ranges_from_store(store: EvidenceStore) -> list[SourceRange]:
    ranges: list[SourceRange] = []
    seen: set[tuple[str, int, int]] = set()

    for chunk in store.list_by_tag():
        if chunk.source_type != "novel":
            continue
        if chunk.metadata.chapter_id is None or chunk.metadata.para_range is None:
            continue

        start_para, end_para = chunk.metadata.para_range
        key = (chunk.metadata.chapter_id, start_para, end_para)
        if key in seen:
            continue
        seen.add(key)
        ranges.append(
            SourceRange(
                chapter_id=chunk.metadata.chapter_id,
                start_para=start_para,
                end_para=end_para,
            )
        )

    return ranges
