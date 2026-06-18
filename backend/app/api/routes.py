from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.episode_planner_agent import EpisodePlannerAgent
from app.agents.episode_writer_agent import EpisodeWriterAgent
from app.agents.story_bible_agent import StoryBibleAgent
from app.ai.tasks.retention_points import RetentionPointTask, attach_retention_points
from app.api.project_state import ProjectState
from app.core.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import SplitChapter, split_chapters, split_novel_text
from app.pipeline.global_scan import run_global_scan
from app.pipeline.scene_generator import generate_screenplay
from app.profiles.loader import ProfileLoadError, ShortDramaProfile, load_profile
from app.rag.chunker import chunk_novel
from app.rag.evidence_store import EvidenceStore
from app.rag.retriever import build_retrieval_context, source_ranges_of
from app.rag.types import RetrievalContext
from app.schema.short_drama import (
    Episode,
    IPDiagnosis,
    Registry,
    RegistryCharacter,
    RegistryLocation,
    RetentionPlan,
    Series,
    SourceChapter,
    SourceLink,
    SourceNovel,
    SourceRange,
    StoryBible,
)
from app.validation.highlight import compute_compression_view, compute_highlight_anchors

router = APIRouter()
_rate_limiter: InMemoryRateLimiter | None = None
DEFAULT_PROFILE_ID = "female_revenge_vertical"


class GenerateRequest(BaseModel):
    """Request body for end-to-end screenplay generation."""

    novel_text: str = Field(..., min_length=1)
    title: str = Field(default="AI 改编剧本", min_length=1)
    logline: str | None = None
    profile: Literal["film", "series", "short_drama"] = "film"
    max_json_repair_attempts: int = Field(default=1, ge=0, le=3)
    max_schema_repair_attempts: int = Field(default=1, ge=0, le=3)


class GenerateResponse(BaseModel):
    """Serializable API response for the generation pipeline."""

    screenplay: dict[str, Any]
    global_scan: dict[str, Any]
    lint_findings: list[dict[str, Any]]
    metrics: dict[str, Any]


class HighlightPreviewRequest(BaseModel):
    """Read-only request for F14/F3 source highlight preview data."""

    episode: Episode
    evidence_store: dict[str, Any]


class BootstrapProjectRequest(BaseModel):
    """Create the initial frontend-held V1 project state."""

    novel_text: str = Field(..., min_length=1)
    title: str = Field(default="Untitled Project", min_length=1)
    registry: Registry | None = None
    profile_id: str | None = None


class DiagnoseProjectRequest(ProjectState):
    """ProjectState plus action-only fields for IP diagnosis."""

    profile_id: str | None = None


class StoryBibleProjectRequest(ProjectState):
    """ProjectState plus action-only fields for story bible generation."""

    existing_bible: StoryBible | None = None


class PlanProjectRequest(ProjectState):
    """ProjectState plus action-only fields for episode planning."""

    profile_id: str | None = None


class WriteProjectRequest(ProjectState):
    """ProjectState plus action-only fields for episode writing."""

    profile_id: str | None = None
    max_episodes: int = Field(default=3, ge=0, le=10)


class EpisodeHighlightRequest(ProjectState):
    """ProjectState plus an episode selector for highlight data."""

    episode_number: int = Field(ge=1)


def get_llm_client() -> LLMClient:
    """Create LLM client from environment variables.

    DEMO_MODE=1 forces replay mode so evaluators can run the demo without API keys.
    """
    repo_root = Path(__file__).resolve().parents[3]
    default_recordings_dir = repo_root / "examples" / "llm_recordings"

    demo_mode = os.getenv("DEMO_MODE", "0").lower() in {"1", "true", "yes", "on"}
    llm_mode = os.getenv("LLM_MODE", "live").lower()
    recordings_dir = Path(os.getenv("LLM_RECORDINGS_DIR", str(default_recordings_dir)))

    if demo_mode:
        return LLMClient(mode="replay", recordings_dir=recordings_dir)

    if llm_mode == "replay":
        return LLMClient(mode=llm_mode, recordings_dir=recordings_dir)

    if llm_mode not in {"live", "record"}:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_configuration_error",
                "message": "Unsupported LLM_MODE. Use live, record, or replay.",
                "missing": [],
            },
        )

    config = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY", "").strip(),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL", "").strip(),
        "LLM_MODEL": os.getenv("LLM_MODEL", "").strip(),
    }
    missing = [name for name, value in config.items() if not value]
    if missing:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_configuration_error",
                "message": "Missing server-side LLM configuration.",
                "missing": missing,
            },
        )

    return LLMClient(
        base_url=config["LLM_BASE_URL"],
        model=config["LLM_MODEL"],
        api_key=config["LLM_API_KEY"],
        mode=llm_mode,
        recordings_dir=recordings_dir,
    )


def get_rate_limiter() -> InMemoryRateLimiter:
    global _rate_limiter

    limit_per_day = _rate_limit_per_day()
    if _rate_limiter is None or _rate_limiter.limit_per_day != limit_per_day:
        _rate_limiter = InMemoryRateLimiter(limit_per_day=limit_per_day)
    return _rate_limiter


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/highlight-preview")
def highlight_preview_api(
    request: HighlightPreviewRequest = Body(...),
) -> dict[str, Any]:
    store = EvidenceStore.from_json(request.evidence_store)
    return {
        "highlight_anchors": jsonable_encoder(
            compute_highlight_anchors(request.episode, store)
        ),
        "compression_view": jsonable_encoder(
            compute_compression_view(request.episode, store)
        ),
    }


@router.post("/v1/project/bootstrap", response_model=ProjectState)
def bootstrap_project_api(
    request: BootstrapProjectRequest,
    raw_request: Request,
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> ProjectState:
    try:
        chapters = split_chapters(request.novel_text, min_chapters=1)
        novel = _source_novel_from_chapters(
            title=request.title,
            chapters=chapters,
        )
        registry = request.registry or _scan_registry_for_bootstrap(
            chapters=chapters,
            raw_request=raw_request,
            rate_limiter=rate_limiter,
        )
        store = EvidenceStore()
        store.add_chunks(chunk_novel(novel, registry=registry))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": exc.__class__.__name__, "message": str(exc)},
        ) from exc

    return ProjectState(
        project_id=_stable_project_id(request.title, request.novel_text),
        novel=novel,
        registry=registry,
        evidence_store=store.to_json(),
    )


@router.post("/v1/diagnose", response_model=ProjectState)
def diagnose_project_api(
    request: DiagnoseProjectRequest,
    raw_request: Request,
    client: LLMClient = Depends(get_llm_client),
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> ProjectState:
    _check_rate_limit(raw_request, client, rate_limiter)
    state = _project_state_from_action_request(request, exclude={"profile_id"})
    store = EvidenceStore.from_json(state.evidence_store)
    profile_ids = [] if client.mode == "replay" else _profile_id_list(request.profile_id)

    run = DiagnosisAgent(
        store=store,
        llm_client=client,
        profile_ids=profile_ids,
    ).run(
        project_id=state.project_id,
        source_novel=state.novel,
        registry=state.registry,
    )

    if run.status != "success" or not isinstance(run.output, IPDiagnosis):
        raise _agent_failed("diagnosis", run)

    return state.model_copy(
        update={
            "ip_diagnosis": run.output,
            "evidence_store": store.to_json(),
        }
    )


@router.post("/v1/story-bible", response_model=ProjectState)
def story_bible_project_api(
    request: StoryBibleProjectRequest,
    raw_request: Request,
    client: LLMClient = Depends(get_llm_client),
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> ProjectState:
    _check_rate_limit(raw_request, client, rate_limiter)
    state = _project_state_from_action_request(request, exclude={"existing_bible"})
    store = EvidenceStore.from_json(state.evidence_store)

    run = StoryBibleAgent(store=store, llm_client=client).run(
        project_id=state.project_id,
        source_novel=state.novel,
        registry=state.registry,
        existing_bible=request.existing_bible or state.story_bible,
    )

    if run.status != "success" or not isinstance(run.output, StoryBible):
        raise _agent_failed("story_bible", run)

    return state.model_copy(
        update={
            "story_bible": run.output,
            "evidence_store": store.to_json(),
        }
    )


@router.post("/v1/plan", response_model=ProjectState)
def plan_project_api(
    request: PlanProjectRequest,
    raw_request: Request,
    client: LLMClient = Depends(get_llm_client),
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> ProjectState:
    _check_rate_limit(raw_request, client, rate_limiter)
    state = _project_state_from_action_request(request, exclude={"profile_id"})
    store = EvidenceStore.from_json(state.evidence_store)
    profile = _load_profile_or_400(request.profile_id)
    series = _series_for_state(state)

    run = EpisodePlannerAgent(
        store=store,
        registry=state.registry,
        profile=profile,
        llm_client=client,
    ).run(project_id=state.project_id, series=series)

    if run.status != "success":
        raise _agent_failed("episode_planner", run)

    return state.model_copy(
        update={
            "series": series,
            "evidence_store": store.to_json(),
        }
    )


@router.post("/v1/write", response_model=ProjectState)
def write_project_api(
    request: WriteProjectRequest,
    raw_request: Request,
    client: LLMClient = Depends(get_llm_client),
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> ProjectState:
    _check_rate_limit(raw_request, client, rate_limiter)
    state = _project_state_from_action_request(
        request,
        exclude={"profile_id", "max_episodes"},
    )
    store = EvidenceStore.from_json(state.evidence_store)
    profile = _load_profile_or_400(request.profile_id)
    series = _series_for_state(state)

    run = EpisodeWriterAgent(
        store=store,
        registry=state.registry,
        profile=profile,
        llm_client=client,
    ).run(
        project_id=state.project_id,
        series=series,
        max_episodes=request.max_episodes,
    )

    if run.status != "success":
        raise _agent_failed("episode_writer", run)

    _attach_retention_points(
        project_id=state.project_id,
        series=series,
        store=store,
        client=client,
    )

    return state.model_copy(
        update={
            "series": series,
            "evidence_store": store.to_json(),
        }
    )


@router.post("/v1/episode-highlight")
def episode_highlight_api(
    request: EpisodeHighlightRequest,
) -> dict[str, Any]:
    state = _project_state_from_action_request(request, exclude={"episode_number"})
    if state.series is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_series",
                "message": "ProjectState.series is required for episode highlight.",
            },
        )

    episode = _episode_by_number(state.series, request.episode_number)
    store = EvidenceStore.from_json(state.evidence_store)
    return {
        "highlight_anchors": jsonable_encoder(
            compute_highlight_anchors(episode, store)
        ),
        "compression_view": jsonable_encoder(
            compute_compression_view(episode, store)
        ),
    }


@router.post("/generate", response_model=GenerateResponse)
def generate_screenplay_api(
    request: GenerateRequest,
    raw_request: Request,
    client: LLMClient = Depends(get_llm_client),
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> GenerateResponse:
    """Run the full backend pipeline.

    novel_text
    -> split chapters
    -> global scan
    -> scene generation
    -> schema validation
    -> linter
    -> response payload
    """
    try:
        rate_limiter.check(_rate_limit_subject(raw_request), llm_mode=client.mode)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=exc.to_detail()) from exc

    try:
        chapters = split_novel_text(request.novel_text)

        global_scan = run_global_scan(client, chapters)

        generation = generate_screenplay(
            client=client,
            chapters=chapters,
            global_scan=global_scan,
            title=request.title,
            logline=request.logline,
            profile=request.profile,
            max_json_repair_attempts=request.max_json_repair_attempts,
            max_schema_repair_attempts=request.max_schema_repair_attempts,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": exc.__class__.__name__,
                "message": str(exc),
            },
        ) from exc

    return GenerateResponse(
        screenplay=generation.screenplay.model_dump(mode="json"),
        global_scan={
            "characters": [_to_jsonable(item) for item in global_scan.characters],
            "locations": [_to_jsonable(item) for item in global_scan.locations],
            "chapter_summaries": dict(global_scan.chapter_summaries),
            "warnings": list(global_scan.warnings),
        },
        lint_findings=[finding.to_dict() for finding in generation.lint_findings],
        metrics=asdict(generation.metrics),
    )


def _source_novel_from_chapters(
    *,
    title: str,
    chapters: list[SplitChapter],
) -> SourceNovel:
    return SourceNovel(
        novel_id="N001",
        title=title,
        chapters=[
            SourceChapter(
                chapter_id=chapter.chapter_id,
                title=chapter.title,
                paragraphs=chapter.paragraphs(),
            )
            for chapter in chapters
        ],
    )


def _scan_registry_for_bootstrap(
    *,
    chapters: list[SplitChapter],
    raw_request: Request,
    rate_limiter: InMemoryRateLimiter,
) -> Registry:
    client = get_llm_client()
    _check_rate_limit(raw_request, client, rate_limiter)
    scan = run_global_scan(client, chapters)
    return Registry(
        characters=[
            RegistryCharacter(
                character_id=character.character_id,
                name=character.name,
                aliases=character.aliases,
                description=character.description,
            )
            for character in scan.characters
        ],
        locations=[
            RegistryLocation(
                location_id=location.location_id,
                name=location.name,
                aliases=location.aliases,
                description=location.description,
            )
            for location in scan.locations
        ],
        relationship_map=[],
    )


def _project_state_from_action_request(
    request: ProjectState,
    *,
    exclude: set[str],
) -> ProjectState:
    return ProjectState.model_validate(request.model_dump(mode="json", exclude=exclude))


def _stable_project_id(title: str, novel_text: str) -> str:
    digest = hashlib.sha256(f"{title}\n{novel_text}".encode("utf-8")).hexdigest()
    return f"project:{digest[:12]}"


def _load_profile_or_400(profile_id: str | None) -> ShortDramaProfile:
    selected_profile_id = (profile_id or DEFAULT_PROFILE_ID).strip()
    try:
        return load_profile(selected_profile_id)
    except ProfileLoadError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "profile_load_error",
                "message": str(exc),
            },
        ) from exc


def _series_for_state(state: ProjectState) -> Series:
    if state.series is not None:
        return state.series

    return Series.model_validate(
        {
            "series_id": "SRS001",
            "title": state.novel.title,
            "episodes": [_placeholder_episode(state).model_dump(mode="json")],
            "outlines": [],
        }
    )


def _placeholder_episode(state: ProjectState) -> Episode:
    source_link = _first_source_link(state.novel)
    return Episode.model_validate(
        {
            "episode_id": "E000",
            "number": 1,
            "title": "Placeholder",
            "logline": "Placeholder before replay writes real episodes.",
            "opening_hook": "Placeholder hook.",
            "main_conflict": "Placeholder conflict.",
            "emotional_payoff": "Placeholder payoff.",
            "cliffhanger": "Placeholder cliffhanger.",
            "source_ranges": [source_link.model_dump(mode="json")],
            "scenes": [
                {
                    "scene_id": "SC000",
                    "source_links": [source_link.model_dump(mode="json")],
                    "beats": [
                        {
                            "beat_id": "B000",
                            "elements": [
                                {
                                    "element_id": "EL000",
                                    "type": "action",
                                    "text": "Placeholder action.",
                                    "source_links": [source_link.model_dump(mode="json")],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def _first_source_link(source_novel: SourceNovel) -> SourceLink:
    first_chapter = source_novel.chapters[0]
    return SourceLink(
        type="source_based",
        source_range=SourceRange(
            chapter_id=first_chapter.chapter_id,
            start_para=1,
            end_para=1,
        ),
    )


def _attach_retention_points(
    *,
    project_id: str,
    series: Series,
    store: EvidenceStore,
    client: LLMClient,
) -> None:
    for episode in series.episodes:
        result = RetentionPointTask(episode=episode, llm_client=client).run(
            _retention_context_for_episode(
                episode=episode,
                store=store,
                series=series,
            ),
            store,
        )
        if (
            result.task_run.validation_report.passed
            and isinstance(result.output, RetentionPlan)
        ):
            attach_retention_points(episode, result.output)
            continue

        raise HTTPException(
            status_code=400,
            detail={
                "error": "retention_points_failed",
                "project_id": project_id,
                "episode_number": episode.number,
                "validation_report": jsonable_encoder(
                    result.task_run.validation_report
                ),
            },
        )


def _retention_context_for_episode(
    *,
    episode: Episode,
    store: EvidenceStore,
    series: Series,
) -> RetrievalContext:
    return build_retrieval_context(
        task_name="retention_points",
        query=f"mark retention points for episode {episode.number}",
        store=store,
        source_ranges=source_ranges_of(episode),
        filters={
            "event_tags": ["story_bible"],
            "episode_number": episode.number,
        },
        profile_context={
            "series": {
                "series_id": series.series_id,
                "title": series.title,
            },
            "episode": {
                "episode_id": episode.episode_id,
                "number": episode.number,
            },
        },
    )


def _episode_by_number(series: Series, episode_number: int) -> Episode:
    for episode in series.episodes:
        if episode.number == episode_number:
            return episode

    raise HTTPException(
        status_code=404,
        detail={
            "error": "episode_not_found",
            "message": f"Episode not found: {episode_number}",
        },
    )


def _profile_id_list(profile_id: str | None) -> list[str]:
    if profile_id is None:
        return []
    cleaned = profile_id.strip()
    return [cleaned] if cleaned else []


def _check_rate_limit(
    request: Request,
    client: LLMClient,
    rate_limiter: InMemoryRateLimiter,
) -> None:
    try:
        rate_limiter.check(_rate_limit_subject(request), llm_mode=client.mode)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=exc.to_detail()) from exc


def _agent_failed(agent_name: str, run: Any) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": f"{agent_name}_agent_failed",
            "status": run.status,
            "steps": jsonable_encoder(run.steps),
        },
    )


def _to_jsonable(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    raise TypeError(f"Cannot serialize value: {value!r}")


def _rate_limit_per_day() -> int:
    raw_value = os.getenv("RATE_LIMIT_PER_DAY", "100").strip()
    try:
        return int(raw_value)
    except ValueError:
        return 100


def _rate_limit_subject(request: Request) -> str:
    session_id = request.headers.get("x-session-id", "").strip()
    if session_id:
        return session_id
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"
