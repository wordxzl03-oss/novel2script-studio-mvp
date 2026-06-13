import json
from pathlib import Path

import pytest

from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import split_novel_text
from app.pipeline.global_scan import (
    GlobalScanError,
    merge_character_candidates,
    merge_location_candidates,
    run_global_scan,
    scan_chapter,
)

ROOT = Path(__file__).resolve().parents[2]


def fake_openai_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


# ----------------------------------------------------- 确定性归并（纯函数）


def test_alias_merge_across_chapters():
    per_chapter = [
        [{"name": "林砚", "aliases": ["砚哥"], "role": "protagonist", "description": "刑警"}],
        [{"name": "林队", "aliases": ["林砚"], "role": "minor", "description": ""}],
    ]
    characters, warnings = merge_character_candidates(per_chapter)

    assert len(characters) == 1
    assert warnings == []
    assert characters[0].character_id == "C001"
    assert characters[0].name == "林砚"
    assert set(characters[0].aliases) == {"砚哥", "林队"}
    assert characters[0].role == "protagonist"  # 高优先级 role 保留


def test_alias_conflict_keeps_characters_separate_with_warning():
    per_chapter = [
        [
            {"name": "林砚", "aliases": ["阿砚"], "role": "protagonist", "description": ""},
            {"name": "周南", "aliases": [], "role": "supporting", "description": ""},
        ],
        # LLM 误把"阿砚"同时归给周南：阿砚已被林砚占用，周南名下还有"老周"
        [{"name": "周南", "aliases": ["阿砚", "老周"], "role": "supporting", "description": ""}],
    ]
    characters, warnings = merge_character_candidates(per_chapter)

    names = {c.name: c for c in characters}
    assert len(characters) == 2
    assert "阿砚" in names["林砚"].aliases
    assert "阿砚" not in names["周南"].aliases  # 冲突称呼不被抢走
    assert "老周" in names["周南"].aliases  # 非冲突称呼正常并入
    assert len(warnings) == 1


def test_description_prefers_longer_text():
    per_chapter = [
        [{"name": "陈叔", "aliases": [], "role": "minor", "description": "管理员"}],
        [{"name": "陈叔", "aliases": [], "role": "minor",
          "description": "档案室管理员，曾参与旧案资料整理"}],
    ]
    characters, _ = merge_character_candidates(per_chapter)
    assert characters[0].description == "档案室管理员，曾参与旧案资料整理"


def test_location_alias_merge():
    per_chapter = [
        [{"name": "巷口", "aliases": ["老街巷口"], "description": "狭窄潮湿"}],
        [{"name": "老街巷口", "aliases": [], "description": ""}],
    ]
    locations, warnings = merge_location_candidates(per_chapter)
    assert len(locations) == 1
    assert locations[0].location_id == "L001"
    assert warnings == []


# ------------------------------------------------- 解析自愈（一次纠错回喂）


def test_scan_chapter_retries_once_on_bad_json():
    chapters = split_novel_text(
        (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    )
    responses = iter(
        [
            "抱歉，这是无法解析的回答",
            json.dumps(
                {"characters": [{"name": "林砚", "aliases": [], "role": "protagonist",
                                 "description": ""}],
                 "locations": [], "summary": "测试摘要"},
                ensure_ascii=False,
            ),
        ]
    )
    calls = {"count": 0}

    def post_fn(url, payload, headers):
        calls["count"] += 1
        return fake_openai_response(next(responses))

    client = LLMClient(base_url="https://example.com/v1", model="m",
                       api_key="k", mode="live", post_fn=post_fn)
    parsed = scan_chapter(client, chapters[0])

    assert calls["count"] == 2
    assert parsed["characters"][0]["name"] == "林砚"


def test_scan_chapter_strips_markdown_code_fence():
    chapters = split_novel_text(
        (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    )
    fenced = "```json\n" + json.dumps(
        {"characters": [], "locations": [], "summary": "ok"}, ensure_ascii=False
    ) + "\n```"
    client = LLMClient(base_url="https://example.com/v1", model="m", api_key="k", mode="live",
                       post_fn=lambda u, p, h: fake_openai_response(fenced))
    parsed = scan_chapter(client, chapters[0])
    assert parsed["summary"] == "ok"


# ------------------------------------------------------------ 端到端整合


CANNED = {
    "第1章": {"characters": [
        {"name": "林砚", "aliases": ["砚哥"], "role": "protagonist", "description": "年轻刑警"}],
        "locations": [{"name": "巷口", "aliases": ["老街巷口"], "description": "老街入口"}],
        "summary": "林砚雨夜收到匿名信。"},
    "第2章": {"characters": [
        {"name": "林队", "aliases": ["林砚"], "role": "minor", "description": ""},
        {"name": "陈叔", "aliases": ["老陈"], "role": "minor", "description": "档案室管理员"}],
        "locations": [{"name": "档案室", "aliases": [], "description": "地下档案室"}],
        "summary": "卷宗证词被涂改。"},
    "第3章": {"characters": [
        {"name": "周南", "aliases": ["阿南"], "role": "supporting", "description": "旧友"}],
        "locations": [{"name": "老街巷口", "aliases": [], "description": ""}],
        "summary": "巷口对峙。"},
}


def canned_post_fn(url, payload, headers):
    user_message = payload["messages"][-1]["content"]
    for marker, data in CANNED.items():
        if marker in user_message:
            return fake_openai_response(json.dumps(data, ensure_ascii=False))
    raise AssertionError(f"未匹配到章节标记：{user_message[:60]}")


def test_run_global_scan_end_to_end():
    chapters = split_novel_text(
        (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    )
    client = LLMClient(base_url="https://example.com/v1", model="m",
                       api_key="k", mode="live", post_fn=canned_post_fn)
    result = run_global_scan(client, chapters)

    # 林砚 / 林队 / 砚哥跨章归一为同一角色
    names = {c.name: c for c in result.characters}
    assert "林砚" in names
    assert set(names["林砚"].aliases) == {"砚哥", "林队"}
    assert len(result.characters) == 3  # 林砚、陈叔、周南

    # 巷口与老街巷口归一为同一地点
    assert len(result.locations) == 2  # 巷口、档案室
    location_names = {l.name for l in result.locations}
    assert "巷口" in location_names

    # 每章摘要齐全；token 用量被记录
    assert set(result.chapter_summaries) == {"CH001", "CH002", "CH003"}
    assert client.usage.calls == 3
    assert client.usage.prompt_tokens > 0


def test_record_mode_creates_replayable_recordings(tmp_path):
    """录制一遍后，无 Key 的回放客户端能完整复现全局扫描（DEMO_MODE 的工作原理）。"""
    chapters = split_novel_text(
        (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    )
    recorder = LLMClient(base_url="https://example.com/v1", model="m",
                         api_key="k", mode="record", recordings_dir=tmp_path,
                         post_fn=canned_post_fn)
    first = run_global_scan(recorder, chapters)

    replayer = LLMClient(mode="replay", recordings_dir=tmp_path)
    second = run_global_scan(replayer, chapters)

    assert [c.name for c in second.characters] == [c.name for c in first.characters]
    assert second.chapter_summaries == first.chapter_summaries
