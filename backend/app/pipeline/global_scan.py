from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import SplitChapter
from app.schema.models import Character, Location

ROLE_PRIORITY = {"protagonist": 3, "antagonist": 2, "supporting": 1, "minor": 0}


class GlobalScanError(ValueError):
    """全局扫描阶段的错误（LLM 输出无法解析等）。"""


_SCAN_SYSTEM_PROMPT = """你是小说改编流水线中的信息抽取器。从给定章节中抽取：
1. characters：本章出场人物。name 使用最正式的称呼；aliases 列出文中出现过的其他称呼（绰号、昵称、职务称呼）。
2. locations：事件发生的具体地点。
3. summary：不超过 80 字的本章情节摘要。
只输出 JSON，不要任何解释、不要 markdown 代码块。格式：
{"characters":[{"name":"","aliases":[],"role":"protagonist|supporting|antagonist|minor","description":""}],"locations":[{"name":"","aliases":[],"description":""}],"summary":""}"""


@dataclass
class GlobalScanResult:
    characters: list[Character]
    locations: list[Location]
    chapter_summaries: dict[str, str]
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------- LLM 候选抽取


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_scan_response(raw: str) -> dict:
    try:
        data = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise GlobalScanError(f"无法解析为 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise GlobalScanError("顶层必须是 JSON 对象")
    for key in ("characters", "locations"):
        if not isinstance(data.get(key, []), list):
            raise GlobalScanError(f"字段 {key} 必须是数组")
    return data


def scan_chapter(client: LLMClient, chapter: SplitChapter) -> dict:
    """对单章做候选抽取；解析失败时把报错回喂模型重试一次（自愈雏形）。"""
    messages = [
        {"role": "system", "content": _SCAN_SYSTEM_PROMPT},
        {"role": "user", "content": f"《{chapter.title}》\n\n{chapter.content}"},
    ]
    raw = client.chat(messages, temperature=0.0)
    try:
        return _parse_scan_response(raw)
    except GlobalScanError as exc:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": f"上面的输出存在问题：{exc}。请重新输出，且只输出合法 JSON。",
            },
        ]
        raw_retry = client.chat(retry_messages, temperature=0.0)
        return _parse_scan_response(raw_retry)


# --------------------------------------------------- 确定性归并（代码负责秩序）


def _normalized_role(value: object) -> str:
    return value if isinstance(value, str) and value in ROLE_PRIORITY else "minor"


def _merge_named_candidates(
    per_chapter: list[list[dict]], *, kind: str, with_role: bool
) -> tuple[list[dict], list[str]]:
    """跨章合并实体候选（确定性，不依赖 LLM）。

    规则：
    - 候选 name 已登记 → 并入该实体；其中被"其他实体"占用的别名属于 LLM 误并，
      丢弃并告警，其余称呼正常并入；
    - 候选 name 未登记、但别名唯一指向某个已登记实体 → 整体并入（跨章改称呼的情形）；
    - 候选 name 未登记、别名指向多个不同实体 → 真冲突：仅保留未被占用的称呼，
      作为独立实体登记并告警；
    - 其余情况 → 登记为新实体。
    """
    merged: list[dict] = []
    claimed: dict[str, int] = {}
    warnings: list[str] = []

    for chapter_index, candidates in enumerate(per_chapter, start=1):
        for candidate in candidates or []:
            name = str(candidate.get("name") or "").strip()
            if not name:
                continue
            aliases = {
                str(a).strip()
                for a in (candidate.get("aliases") or [])
                if str(a).strip() and str(a).strip() != name
            }
            mentions = {name} | aliases
            role = _normalized_role(candidate.get("role")) if with_role else None
            description = str(candidate.get("description") or "").strip() or None

            owner_of_name = claimed.get(name)
            alias_owners = {claimed[a] for a in aliases if a in claimed}

            if owner_of_name is not None:
                target: int | None = owner_of_name
                conflicting = {a for a in aliases if claimed.get(a, target) != target}
                if conflicting:
                    warnings.append(
                        f"第{chapter_index}章{kind}候选「{name}」的称呼 "
                        f"{sorted(conflicting)} 已属于其他{kind}，疑似误并，已丢弃"
                    )
                    mentions -= conflicting
            elif len(alias_owners) == 1:
                target = next(iter(alias_owners))
            elif len(alias_owners) > 1:
                warnings.append(
                    f"第{chapter_index}章{kind}候选「{name}」的别名指向多个已登记{kind}，"
                    f"未合并，仅保留未被占用的称呼"
                )
                mentions = {m for m in mentions if m not in claimed}
                if not mentions:
                    continue
                target = None
            else:
                target = None

            if target is not None:
                entry = merged[target]
                entry["aliases"] |= mentions - {entry["name"]}
                if with_role and ROLE_PRIORITY[role] > ROLE_PRIORITY[entry["role"]]:
                    entry["role"] = role
                if description and len(description) > len(entry["description"] or ""):
                    entry["description"] = description
                index = target
            else:
                index = len(merged)
                entry = {
                    "name": name,
                    "aliases": mentions - {name},
                    "description": description,
                }
                if with_role:
                    entry["role"] = role
                merged.append(entry)

            for mention in mentions:
                claimed[mention] = index

    return merged, warnings


def merge_character_candidates(
    per_chapter: list[list[dict]],
) -> tuple[list[Character], list[str]]:
    merged, warnings = _merge_named_candidates(per_chapter, kind="角色", with_role=True)
    characters = [
        Character(
            character_id=f"C{i:03d}",
            name=entry["name"],
            aliases=sorted(entry["aliases"]),
            role=entry["role"],
            description=entry["description"],
        )
        for i, entry in enumerate(merged, start=1)
    ]
    return characters, warnings


def merge_location_candidates(
    per_chapter: list[list[dict]],
) -> tuple[list[Location], list[str]]:
    merged, warnings = _merge_named_candidates(per_chapter, kind="地点", with_role=False)
    locations = [
        Location(
            location_id=f"L{i:03d}",
            name=entry["name"],
            aliases=sorted(entry["aliases"]),
            description=entry["description"],
        )
        for i, entry in enumerate(merged, start=1)
    ]
    return locations, warnings


# -------------------------------------------------------------- 顶层入口


def run_global_scan(client: LLMClient, chapters: list[SplitChapter]) -> GlobalScanResult:
    """全局扫描：LLM 逐章抽取候选 → 确定性归并出角色/地点注册表与各章摘要。"""
    per_chapter_characters: list[list[dict]] = []
    per_chapter_locations: list[list[dict]] = []
    summaries: dict[str, str] = {}

    for chapter in chapters:
        parsed = scan_chapter(client, chapter)
        per_chapter_characters.append(parsed.get("characters") or [])
        per_chapter_locations.append(parsed.get("locations") or [])
        summaries[chapter.chapter_id] = str(parsed.get("summary") or "").strip()

    characters, character_warnings = merge_character_candidates(per_chapter_characters)
    locations, location_warnings = merge_location_candidates(per_chapter_locations)

    return GlobalScanResult(
        characters=characters,
        locations=locations,
        chapter_summaries=summaries,
        warnings=character_warnings + location_warnings,
    )
