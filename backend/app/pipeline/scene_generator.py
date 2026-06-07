from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from pydantic import ValidationError

from app.linter.engine import lint_screenplay
from app.linter.rules import LintFinding
from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import SplitChapter
from app.pipeline.global_scan import GlobalScanResult
from app.schema.models import Chapter, Character, Location, Screenplay


class SceneGenerationError(ValueError):
    """场景生成阶段错误：LLM 输出无法解析、Schema 校验失败或自愈失败。"""


@dataclass
class GenerationMetrics:
    """生成流水线指标。

    这些指标由代码计算，不由 LLM 直接报告。
    """

    chapter_count: int = 0
    scene_count: int = 0
    llm_calls_before: int = 0
    llm_calls_after: int = 0
    json_repair_attempts: int = 0
    schema_repair_attempts: int = 0
    first_pass_schema_ok: bool = False
    final_schema_ok: bool = False
    lint_error_count: int = 0
    lint_warning_count: int = 0
    lint_info_count: int = 0

    @property
    def llm_calls_used(self) -> int:
        return self.llm_calls_after - self.llm_calls_before


@dataclass
class SceneGenerationResult:
    screenplay: Screenplay
    lint_findings: list[LintFinding] = field(default_factory=list)
    metrics: GenerationMetrics = field(default_factory=GenerationMetrics)
    raw_scene_batches: list[list[dict[str, Any]]] = field(default_factory=list)


_SCENE_SYSTEM_PROMPT = """你是小说改编流水线中的剧本场景生成器。

你的任务：
1. 只根据给定章节文本生成本章剧本场景；
2. 角色必须引用给定角色注册表中的 character_id；
3. 地点必须引用给定地点注册表中的 location_id；
4. 每个场景必须包含 source.chapter 与 source.para_range；
5. para_range 使用章节段落的 1-based 编号；
6. elements 必须是有序列表，保留动作、对白、声音、转场等顺序；
7. 不要编造未注册角色 id、未注册地点 id；
8. 不要输出 estimated_seconds，该字段由代码计算；
9. 只输出 JSON，不要 markdown，不要解释。

输出格式：
{
  "scenes": [
    {
      "scene_id": "S001",
      "title": "",
      "source": {
        "chapter": "CH001",
        "para_range": {"start": 1, "end": 2},
        "fidelity": "faithful",
        "quote": ""
      },
      "heading": {
        "int_ext": "INT|EXT|INT_EXT",
        "location_id": "L001",
        "time_of_day": "day|night|dawn|dusk|unknown"
      },
      "characters": ["C001"],
      "objective": "",
      "conflict": "",
      "elements": [
        {"type": "action", "text": ""},
        {"type": "dialogue", "speaker_id": "C001", "line": "", "mode": "normal"}
      ],
      "adaptation_log": [
        {"change_type": "keep", "reason": ""}
      ]
    }
  ]
}
"""


def generate_screenplay(
    *,
    client: LLMClient,
    chapters: list[SplitChapter],
    global_scan: GlobalScanResult,
    title: str = "AI 改编剧本",
    logline: str | None = None,
    profile: str = "film",
    max_json_repair_attempts: int = 1,
    max_schema_repair_attempts: int = 1,
) -> SceneGenerationResult:
    """Generate a validated Screenplay from chapters and global scan result.

    Pipeline:
    chapters + registry
    -> LLM scene generation per chapter
    -> JSON repair
    -> deterministic payload assembly
    -> Pydantic Screenplay validation
    -> schema repair
    -> Linter findings + metrics
    """
    if not chapters:
        raise SceneGenerationError("chapters 不能为空。")

    metrics = GenerationMetrics(
        chapter_count=len(chapters),
        llm_calls_before=client.usage.calls,
    )

    raw_scene_batches: list[list[dict[str, Any]]] = []
    for chapter in chapters:
        scenes, json_repairs = generate_scenes_for_chapter(
            client=client,
            chapter=chapter,
            global_scan=global_scan,
            max_json_repair_attempts=max_json_repair_attempts,
        )
        metrics.json_repair_attempts += json_repairs
        raw_scene_batches.append(scenes)

    flat_scenes = _normalize_scene_ids(_flatten(raw_scene_batches))
    payload = _build_screenplay_payload(
        title=title,
        logline=logline,
        profile=profile,
        chapters=chapters,
        global_scan=global_scan,
        scenes=flat_scenes,
    )

    try:
        screenplay = Screenplay.model_validate(payload)
        metrics.first_pass_schema_ok = True
        metrics.final_schema_ok = True
    except ValidationError as exc:
        metrics.first_pass_schema_ok = False

        if max_schema_repair_attempts <= 0:
            raise SceneGenerationError(f"Screenplay Schema 校验失败：{exc}") from exc

        metrics.schema_repair_attempts += 1
        repaired_scenes = repair_scenes_for_schema(
            client=client,
            payload=payload,
            validation_error=str(exc),
        )
        repaired_scenes = _normalize_scene_ids(repaired_scenes)
        payload = _build_screenplay_payload(
            title=title,
            logline=logline,
            profile=profile,
            chapters=chapters,
            global_scan=global_scan,
            scenes=repaired_scenes,
        )

        try:
            screenplay = Screenplay.model_validate(payload)
        except ValidationError as repair_exc:
            raise SceneGenerationError(
                f"Schema 自愈后仍然校验失败：{repair_exc}"
            ) from repair_exc

        metrics.final_schema_ok = True
        raw_scene_batches = [repaired_scenes]

    lint_findings = lint_screenplay(screenplay)

    metrics.scene_count = len(screenplay.scenes)
    metrics.llm_calls_after = client.usage.calls
    metrics.lint_error_count = sum(1 for f in lint_findings if f.severity == "error")
    metrics.lint_warning_count = sum(1 for f in lint_findings if f.severity == "warning")
    metrics.lint_info_count = sum(1 for f in lint_findings if f.severity == "info")

    return SceneGenerationResult(
        screenplay=screenplay,
        lint_findings=lint_findings,
        metrics=metrics,
        raw_scene_batches=raw_scene_batches,
    )


def generate_scenes_for_chapter(
    *,
    client: LLMClient,
    chapter: SplitChapter,
    global_scan: GlobalScanResult,
    max_json_repair_attempts: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    """Generate scenes for one chapter; retry once when JSON is invalid."""
    messages = _build_chapter_scene_messages(chapter, global_scan)
    raw = client.chat(messages, temperature=0.0)

    try:
        return _parse_scene_response(raw), 0
    except SceneGenerationError as exc:
        if max_json_repair_attempts <= 0:
            raise

        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    f"上面的输出无法解析：{exc}。"
                    "请重新输出合法 JSON，且只输出 {\"scenes\": [...]}。"
                ),
            },
        ]
        raw_retry = client.chat(retry_messages, temperature=0.0)
        return _parse_scene_response(raw_retry), 1


def repair_scenes_for_schema(
    *,
    client: LLMClient,
    payload: dict[str, Any],
    validation_error: str,
) -> list[dict[str, Any]]:
    """Ask LLM to repair scene list after Pydantic validation failure."""
    messages = [
        {
            "role": "system",
            "content": (
                "你是剧本 YAML Schema 修复器。"
                "你只能修复 scenes 字段，不得修改角色注册表、地点注册表和章节注册表。"
                "必须只输出 JSON：{\"scenes\": [...]}。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "schema_error": validation_error,
                    "allowed_characters": payload["characters"],
                    "allowed_locations": payload["locations"],
                    "allowed_chapters": payload["chapters"],
                    "current_scenes": payload["scenes"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        },
    ]

    raw = client.chat(messages, temperature=0.0)
    return _parse_scene_response(raw)


# ---------------------------------------------------------------------
# Prompt construction


def _build_chapter_scene_messages(
    chapter: SplitChapter,
    global_scan: GlobalScanResult,
) -> list[dict[str, str]]:
    registry = {
        "characters": [_model_to_dict(c) for c in global_scan.characters],
        "locations": [_model_to_dict(l) for l in global_scan.locations],
        "chapter_summary": global_scan.chapter_summaries.get(chapter.chapter_id, ""),
    }

    paragraphs = [
        {
            "para_no": index,
            "text": text,
        }
        for index, text in enumerate(_chapter_paragraphs(chapter), start=1)
    ]

    user_payload = {
        "chapter": {
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "paragraphs": paragraphs,
        },
        "registry": registry,
        "requirements": {
            "scene_source_chapter": chapter.chapter_id,
            "scene_id_rule": "Use S001, S002... globally if known; otherwise any unique Sxxx id is acceptable.",
            "do_not_output_estimated_seconds": True,
        },
    }

    return [
        {"role": "system", "content": _SCENE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
        },
    ]


# ---------------------------------------------------------------------
# Parsing / assembly


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_scene_response(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise SceneGenerationError(f"无法解析场景 JSON：{exc}") from exc

    if isinstance(data, list):
        scenes = data
    elif isinstance(data, dict) and isinstance(data.get("scenes"), list):
        scenes = data["scenes"]
    else:
        raise SceneGenerationError("场景生成结果必须是数组，或包含 scenes 数组的对象。")

    if not scenes:
        raise SceneGenerationError("场景生成结果为空。")

    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise SceneGenerationError(f"scenes[{index}] 必须是对象。")

    return scenes


def _build_screenplay_payload(
    *,
    title: str,
    logline: str | None,
    profile: str,
    chapters: list[SplitChapter],
    global_scan: GlobalScanResult,
    scenes: list[dict[str, Any]],
) -> dict[str, Any]:
    chapter_models = [
        Chapter(
            chapter_id=chapter.chapter_id,
            title=chapter.title,
            summary=global_scan.chapter_summaries.get(chapter.chapter_id, ""),
        )
        for chapter in chapters
    ]

    normalized_scenes = []
    for scene in scenes:
        normalized = dict(scene)
        normalized["estimated_seconds"] = _estimate_scene_seconds(scene)
        normalized_scenes.append(normalized)

    payload: dict[str, Any] = {
        "title": title,
        "metadata": {
            "version": "0.1.0",
            "language": "zh-CN",
            "profile": profile,
        },
        "characters": [_model_to_dict(c) for c in global_scan.characters],
        "locations": [_model_to_dict(l) for l in global_scan.locations],
        "chapters": [_model_to_dict(c) for c in chapter_models],
        "scenes": normalized_scenes,
    }

    if logline:
        payload["logline"] = logline

    return payload


def _normalize_scene_ids(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure scene_id is present and unique without changing scene content."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, scene in enumerate(scenes, start=1):
        item = dict(scene)
        scene_id = str(item.get("scene_id") or "").strip()

        if not scene_id:
            scene_id = f"S{index:03d}"

        if scene_id in seen:
            scene_id = f"S{index:03d}"

        item["scene_id"] = scene_id
        seen.add(scene_id)
        normalized.append(item)

    return normalized


def _flatten(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [scene for batch in batches for scene in batch]


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Cannot serialize value: {value!r}")


def _chapter_paragraphs(chapter: SplitChapter) -> list[str]:
    paragraphs_method = getattr(chapter, "paragraphs", None)
    if callable(paragraphs_method):
        paragraphs = paragraphs_method()
    else:
        paragraphs = [p.strip() for p in chapter.content.splitlines() if p.strip()]

    return [str(p).strip() for p in paragraphs if str(p).strip()]


def _estimate_scene_seconds(scene: Mapping[str, Any]) -> int:
    total = 0
    elements = scene.get("elements")
    if not isinstance(elements, list):
        return 0

    for element in elements:
        if not isinstance(element, Mapping):
            continue

        element_type = element.get("type")
        if element_type == "dialogue":
            total += max(2, len(str(element.get("line") or "")) // 5)
        elif element_type == "action":
            total += max(3, len(str(element.get("text") or "")) // 8)
        elif element_type == "transition":
            total += 1
        elif element_type == "sound":
            total += 2
        elif element_type == "title_card":
            total += 2

    return total