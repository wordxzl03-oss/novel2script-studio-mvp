from __future__ import annotations

from typing import Any

from app.agents.base import AgentRun, AgentStep, BoundedAgent
from app.ai.tasks.episode_script import EpisodeScriptTask
from app.profiles.loader import ShortDramaProfile
from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import EmptyRetrievalError, build_retrieval_context
from app.schema.short_drama import Episode, EpisodeOutline, Registry, Series, SourceRange


class EpisodeWriterAgent(BoundedAgent):
    allowed_steps = [
        "select_outline",
        "retrieve_context",
        "run_script",
        "store_episode",
        "validate",
    ]

    def __init__(
        self,
        *,
        store: EvidenceStore,
        registry: Registry,
        profile: ShortDramaProfile,
        llm_client: Any | None = None,
    ) -> None:
        super().__init__(
            agent_name="episode_writer_agent",
            allowed_steps=self.allowed_steps,
        )
        self.store = store
        self.registry = registry
        self.profile = profile
        self.llm_client = llm_client

    def run(
        self,
        *,
        project_id: str,
        series: Series,
        max_episodes: int = 3,
    ) -> AgentRun:
        self.validate_step_order(
            [
                "select_outline",
                "retrieve_context",
                "run_script",
                "store_episode",
                "validate",
            ]
        )

        steps: list[AgentStep] = []
        generated_episodes: list[Episode] = []
        selected_outlines = series.outlines[: max(max_episodes, 0)]
        failure_count = 0

        for outline in selected_outlines:
            steps.append(
                AgentStep(
                    step_name="select_outline",
                    status="success",
                    message=f"selected episode outline {outline.number}",
                )
            )

            try:
                retrieval_context = build_retrieval_context(
                    task_name="episode_script",
                    query=_script_query(series, outline),
                    store=self.store,
                    source_ranges=_source_ranges_from_outline(outline),
                    filters={
                        "event_tags": ["story_bible"],
                        "episode_number": outline.number,
                    },
                    profile_context={
                        "series": {
                            "series_id": series.series_id,
                            "title": series.title,
                        },
                        "outline": outline.model_dump(mode="json"),
                    },
                )
            except EmptyRetrievalError as exc:
                failure_count += 1
                steps.extend(
                    [
                        AgentStep(
                            step_name="retrieve_context",
                            status="failed",
                            message=str(exc),
                        ),
                        AgentStep(
                            step_name="run_script",
                            status="skipped",
                            message="retrieval failed",
                        ),
                        AgentStep(
                            step_name="store_episode",
                            status="skipped",
                            message="script task did not run",
                        ),
                    ]
                )
                continue

            steps.append(
                AgentStep(
                    step_name="retrieve_context",
                    status="success",
                    message=(
                        f"retrieved {len(retrieval_context.evidence_chunks)} "
                        f"script evidence chunks for episode {outline.number}"
                    ),
                )
            )

            task = EpisodeScriptTask(
                llm_client=self.llm_client,
                outline=outline,
                registry=self.registry,
                profile=self.profile,
            )
            task_result = task.run(retrieval_context, self.store)
            task_passed = task_result.task_run.validation_report.passed
            steps.append(
                AgentStep(
                    step_name="run_script",
                    task_run=task_result.task_run,
                    status="success" if task_passed else "failed",
                    message=task_result.task_run.status,
                )
            )

            if not task_passed or not isinstance(task_result.output, Episode):
                failure_count += 1
                steps.append(
                    AgentStep(
                        step_name="store_episode",
                        status="skipped",
                        message="script validation failed",
                    )
                )
                continue

            generated_episodes.append(task_result.output)
            steps.append(
                AgentStep(
                    step_name="store_episode",
                    status="success",
                    message=f"stored episode {task_result.output.number}",
                )
            )

        series.episodes = generated_episodes
        status = _agent_status(
            selected_count=len(selected_outlines),
            generated_count=len(generated_episodes),
            failure_count=failure_count,
        )
        steps.append(
            AgentStep(
                step_name="validate",
                status="success" if status == "success" else "failed",
                message=(
                    f"stored {len(generated_episodes)} of "
                    f"{len(selected_outlines)} selected episodes"
                ),
            )
        )

        return AgentRun(
            agent_name=self.agent_name,
            project_id=project_id,
            target_id=series.series_id,
            steps=steps,
            final_output_ref=(
                f"series:{series.series_id}:episodes:{len(generated_episodes)}"
                if generated_episodes
                else None
            ),
            status=status,
        )


def _source_ranges_from_outline(outline: EpisodeOutline) -> list[SourceRange]:
    return [
        source_link.source_range
        for source_link in outline.source_ranges
        if source_link.source_range is not None
    ]


def _script_query(series: Series, outline: EpisodeOutline) -> str:
    title = outline.title or series.title
    return f"write episode {outline.number} script: {title}"


def _agent_status(
    *,
    selected_count: int,
    generated_count: int,
    failure_count: int,
) -> str:
    if selected_count == 0 or generated_count == 0:
        return "failed"
    if failure_count:
        return "partial"
    return "success"
