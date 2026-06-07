from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import split_novel_text
from app.pipeline.global_scan import run_global_scan
from app.pipeline.scene_generator import generate_screenplay


router = APIRouter()


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
    """Dependency factory.

    Tests can override this dependency so API tests never require a real API key.
    Runtime config is read by LLMClient from environment variables.
    """
    return LLMClient()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/generate", response_model=GenerateResponse)
def generate_screenplay_api(
    request: GenerateRequest,
    client: LLMClient = Depends(get_llm_client),
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