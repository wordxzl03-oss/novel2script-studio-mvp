from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.linter.rules import LintFinding, RULES


DEFAULT_SHORT_DRAMA_EPISODE_SECONDS_LIMIT = 120
LONG_ACTION_CHAR_LIMIT = 80
LONG_DIALOGUE_CHAR_LIMIT = 60

UNFILMABLE_ACTION_TERMS = (
    "想起",
    "心想",
    "觉得",
    "意识到",
    "明白",
    "回忆起",
    "感到",
    "内心",
    "脑海",
    "仿佛",
)


def lint_screenplay(
    screenplay: Any,
    *,
    short_drama_episode_seconds_limit: int = DEFAULT_SHORT_DRAMA_EPISODE_SECONDS_LIMIT,
) -> list[LintFinding]:
    """Run screenplay linter and return all findings.

    Unlike Pydantic validation, the linter should not fail fast. It scans the
    whole object and returns a complete findings list for UI display, quality
    metrics, and one-click repair.
    """
    data = _to_plain_dict(screenplay)
    findings: list[LintFinding] = []

    characters = _as_list(data.get("characters"))
    locations = _as_list(data.get("locations"))
    scenes = _as_list(data.get("scenes"))
    episodes = _as_list(data.get("episodes"))

    character_ids = {
        str(character.get("character_id")).strip()
        for character in characters
        if _is_non_empty(character.get("character_id"))
    }
    location_ids = {
        str(location.get("location_id")).strip()
        for location in locations
        if _is_non_empty(location.get("location_id"))
    }

    findings.extend(_lint_scene_ids(scenes))
    findings.extend(_lint_scene_source(scenes))
    findings.extend(_lint_heading_locations(scenes, location_ids))
    findings.extend(_lint_dialogues(scenes, character_ids))
    findings.extend(_lint_quality_warnings(scenes, characters))

    if _profile(data) == "short_drama":
        findings.extend(
            _lint_short_drama_episodes(
                episodes=episodes,
                scenes=scenes,
                seconds_limit=short_drama_episode_seconds_limit,
            )
        )

    return findings


def lint_to_dicts(screenplay: Any) -> list[dict[str, str | None]]:
    return [finding.to_dict() for finding in lint_screenplay(screenplay)]


# ---------------------------------------------------------------------------
# E-level rules


def _lint_scene_ids(scenes: list[dict[str, Any]]) -> list[LintFinding]:
    findings: list[LintFinding] = []
    seen: dict[str, int] = {}

    for scene_index, scene in enumerate(scenes):
        scene_id = scene.get("scene_id")

        if not _is_non_empty(scene_id):
            findings.append(
                _finding(
                    "E002",
                    path=f"scenes[{scene_index}].scene_id",
                    message="场景缺少 scene_id。",
                    suggestion="为该场景补充唯一的 scene_id，例如 S001。",
                )
            )
            continue

        scene_id_text = str(scene_id).strip()
        if scene_id_text in seen:
            findings.append(
                _finding(
                    "E002",
                    path=f"scenes[{scene_index}].scene_id",
                    message=(
                        f"场景 id {scene_id_text!r} 重复；首次出现于 "
                        f"scenes[{seen[scene_id_text]}]。"
                    ),
                    suggestion="为重复场景重新分配唯一 scene_id。",
                )
            )
        else:
            seen[scene_id_text] = scene_index

    return findings


def _lint_scene_source(scenes: list[dict[str, Any]]) -> list[LintFinding]:
    findings: list[LintFinding] = []

    for scene_index, scene in enumerate(scenes):
        source = scene.get("source")

        if not isinstance(source, Mapping):
            findings.append(
                _finding(
                    "E004",
                    path=f"scenes[{scene_index}].source",
                    message="场景缺少 source 对象。",
                    suggestion="补充 source.chapter 与 source.para_range。",
                )
            )
            continue

        chapter = source.get("chapter")
        para_range = source.get("para_range")

        if not _is_non_empty(chapter):
            findings.append(
                _finding(
                    "E004",
                    path=f"scenes[{scene_index}].source.chapter",
                    message="场景 source 缺少 chapter。",
                    suggestion="将该场景绑定到来源章节，例如 CH001。",
                )
            )

        if not isinstance(para_range, Mapping):
            findings.append(
                _finding(
                    "E004",
                    path=f"scenes[{scene_index}].source.para_range",
                    message="场景 source 缺少 para_range。",
                    suggestion="补充原文段落区间，例如 {start: 1, end: 3}。",
                )
            )
            continue

        if not _is_positive_int(para_range.get("start")) or not _is_positive_int(
            para_range.get("end")
        ):
            findings.append(
                _finding(
                    "E004",
                    path=f"scenes[{scene_index}].source.para_range",
                    message="para_range.start 与 para_range.end 必须是正整数。",
                    suggestion="使用 1-based 段落编号，例如 start=1, end=3。",
                )
            )
            continue

        if int(para_range["end"]) < int(para_range["start"]):
            findings.append(
                _finding(
                    "E004",
                    path=f"scenes[{scene_index}].source.para_range",
                    message="para_range.end 不能小于 para_range.start。",
                    suggestion="修正段落区间顺序。",
                )
            )

    return findings


def _lint_heading_locations(
    scenes: list[dict[str, Any]],
    location_ids: set[str],
) -> list[LintFinding]:
    findings: list[LintFinding] = []

    for scene_index, scene in enumerate(scenes):
        heading = scene.get("heading")

        if not isinstance(heading, Mapping):
            findings.append(
                _finding(
                    "E005",
                    path=f"scenes[{scene_index}].heading",
                    message="场景缺少 heading 对象。",
                    suggestion="补充 heading.location_id、int_ext 与 time_of_day。",
                )
            )
            continue

        location_id = heading.get("location_id")
        if not _is_non_empty(location_id):
            findings.append(
                _finding(
                    "E005",
                    path=f"scenes[{scene_index}].heading.location_id",
                    message="heading 缺少 location_id。",
                    suggestion="为该场景选择一个已注册地点。",
                )
            )
            continue

        location_id_text = str(location_id).strip()
        if location_id_text not in location_ids:
            findings.append(
                _finding(
                    "E005",
                    path=f"scenes[{scene_index}].heading.location_id",
                    message=f"heading 引用了未注册地点 {location_id_text!r}。",
                    suggestion="将 location_id 改为 locations 注册表中的地点，或先注册该地点。",
                )
            )

    return findings


def _lint_dialogues(
    scenes: list[dict[str, Any]],
    character_ids: set[str],
) -> list[LintFinding]:
    findings: list[LintFinding] = []

    for scene_index, scene in enumerate(scenes):
        scene_character_ids = {
            str(character_id).strip()
            for character_id in _as_list(scene.get("characters"))
            if _is_non_empty(character_id)
        }

        for element_index, element in enumerate(_as_list(scene.get("elements"))):
            if element.get("type") != "dialogue":
                continue

            speaker_id = element.get("speaker_id")
            path = f"scenes[{scene_index}].elements[{element_index}].speaker_id"

            if not _is_non_empty(speaker_id):
                findings.append(
                    _finding(
                        "E001",
                        path=path,
                        message="对白元素缺少 speaker_id。",
                        suggestion="为该对白绑定一个已注册角色 id。",
                    )
                )
                continue

            speaker_id_text = str(speaker_id).strip()

            if speaker_id_text not in character_ids:
                findings.append(
                    _finding(
                        "E001",
                        path=path,
                        message=f"对白引用了未注册角色 {speaker_id_text!r}。",
                        suggestion="将 speaker_id 替换为已注册角色，或先注册该角色。",
                    )
                )
                continue

            if speaker_id_text not in scene_character_ids:
                findings.append(
                    _finding(
                        "E003",
                        path=path,
                        message=(
                            f"对白角色 {speaker_id_text!r} 未出现在该场 "
                            "scene.characters 中。"
                        ),
                        suggestion="将该角色加入 scene.characters，或修改 speaker_id。",
                    )
                )

    return findings


def _lint_short_drama_episodes(
    *,
    episodes: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    seconds_limit: int,
) -> list[LintFinding]:
    findings: list[LintFinding] = []

    if not episodes:
        findings.append(
            _finding(
                "E006",
                path="episodes",
                message="short_drama profile 缺少 episodes。",
                suggestion="为短剧添加至少一集，并补充集末钩子。",
            )
        )
        return findings

    scene_by_id = {
        str(scene.get("scene_id")).strip(): scene
        for scene in scenes
        if _is_non_empty(scene.get("scene_id"))
    }

    for episode_index, episode in enumerate(episodes):
        hook = episode.get("hook") or episode.get("ending_hook")
        if not _is_non_empty(hook):
            findings.append(
                _finding(
                    "E006",
                    path=f"episodes[{episode_index}].hook",
                    message="short_drama 单集缺少集末钩子。",
                    suggestion="补充 hook / ending_hook，用于短剧分集卡点。",
                )
            )

        estimated_seconds = _episode_estimated_seconds(episode, scene_by_id)
        if estimated_seconds is not None and estimated_seconds > seconds_limit:
            findings.append(
                _finding(
                    "E007",
                    path=f"episodes[{episode_index}]",
                    message=(
                        f"short_drama 单集估时 {estimated_seconds} 秒，"
                        f"超过上限 {seconds_limit} 秒。"
                    ),
                    suggestion="压缩场景、减少长对白，或拆分为多集。",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# W / I level rules


def _lint_quality_warnings(
    scenes: list[dict[str, Any]],
    characters: list[dict[str, Any]],
) -> list[LintFinding]:
    findings: list[LintFinding] = []

    character_presence = Counter()

    for scene_index, scene in enumerate(scenes):
        for character_id in _as_list(scene.get("characters")):
            if _is_non_empty(character_id):
                character_presence[str(character_id).strip()] += 1

        for element_index, element in enumerate(_as_list(scene.get("elements"))):
            element_type = element.get("type")

            if element_type == "action":
                text = _text_value(element, "text")
                path = f"scenes[{scene_index}].elements[{element_index}].text"

                if len(text) > LONG_ACTION_CHAR_LIMIT:
                    findings.append(
                        _finding(
                            "W001",
                            path=path,
                            message=f"动作块长度为 {len(text)} 字，超过建议上限。",
                            suggestion="拆分为多个可拍动作，减少小说式描述。",
                        )
                    )

                matched_terms = [term for term in UNFILMABLE_ACTION_TERMS if term in text]
                if matched_terms:
                    findings.append(
                        _finding(
                            "W002",
                            path=path,
                            message=(
                                "动作描写包含不可直接拍摄的心理 / 认知表达："
                                f"{matched_terms}。"
                            ),
                            suggestion="改写为可观察的动作、表情、声音或道具反应。",
                        )
                    )

            elif element_type == "dialogue":
                line = _text_value(element, "line")
                if len(line) > LONG_DIALOGUE_CHAR_LIMIT:
                    findings.append(
                        _finding(
                            "W003",
                            path=f"scenes[{scene_index}].elements[{element_index}].line",
                            message=f"单句台词长度为 {len(line)} 字，超过建议上限。",
                            suggestion="拆分台词或改为动作 / 反应。",
                        )
                    )

        if not _is_non_empty(scene.get("objective")) or not _is_non_empty(
            scene.get("conflict")
        ):
            findings.append(
                _finding(
                    "I001",
                    path=f"scenes[{scene_index}]",
                    message="场景缺少 objective 或 conflict。",
                    suggestion="补充戏剧目标与冲突，便于后续质量分析。",
                )
            )

    for character_index, character in enumerate(characters):
        character_id = character.get("character_id")
        if not _is_non_empty(character_id):
            continue

        character_id_text = str(character_id).strip()
        if character_presence[character_id_text] == 1:
            findings.append(
                _finding(
                    "W004",
                    path=f"characters[{character_index}]",
                    message=f"角色 {character_id_text!r} 只在一个场景中出现。",
                    suggestion="检查是否为别名未归一、无效角色，或确属一次性角色。",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Helpers


def _finding(
    rule_id: str,
    *,
    path: str,
    message: str,
    suggestion: str | None = None,
) -> LintFinding:
    rule = RULES[rule_id]
    return LintFinding(
        rule_id=rule.rule_id,
        severity=rule.severity,
        path=path,
        message=message,
        suggestion=suggestion,
    )


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("lint_screenplay expects a dict-like object or a Pydantic model.")


def _profile(data: Mapping[str, Any]) -> str:
    metadata = data.get("metadata")
    if isinstance(metadata, Mapping):
        return str(metadata.get("profile") or "film")
    return "film"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_non_empty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _is_positive_int(value: Any) -> bool:
    try:
        return int(value) >= 1
    except (TypeError, ValueError):
        return False


def _text_value(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    return str(value or "")


def _episode_estimated_seconds(
    episode: Mapping[str, Any],
    scene_by_id: Mapping[str, Mapping[str, Any]],
) -> int | None:
    explicit = (
        episode.get("estimated_seconds")
        or episode.get("duration_seconds")
        or episode.get("estimate_seconds")
    )

    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            return None

    scene_ids = _as_list(episode.get("scene_ids"))
    if not scene_ids:
        return None

    total = 0
    for scene_id in scene_ids:
        scene = scene_by_id.get(str(scene_id).strip())
        if scene is None:
            continue
        total += _estimate_scene_seconds(scene)

    return total if total > 0 else None


def _estimate_scene_seconds(scene: Mapping[str, Any]) -> int:
    total = 0

    for element in _as_list(scene.get("elements")):
        if element.get("type") == "dialogue":
            total += max(2, len(_text_value(element, "line")) // 5)
        elif element.get("type") == "action":
            total += max(3, len(_text_value(element, "text")) // 8)
        elif element.get("type") == "transition":
            total += 1
        elif element.get("type") == "sound":
            total += 2
        elif element.get("type") == "title_card":
            total += 2

    return total