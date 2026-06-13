from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import split_novel_text
from app.pipeline.global_scan import run_global_scan
from app.pipeline.scene_generator import generate_screenplay
import os
from pathlib import Path

router = APIRouter()
_rate_limiter: InMemoryRateLimiter | None = None


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
