import json
from pathlib import Path

import pytest

from app.llm.client import LLMClient
from app.pipeline.chapter_splitter import split_novel_text
from app.pipeline.global_scan import GlobalScanResult
from app.pipeline.scene_generator import (
    SceneGenerationError,
    generate_scenes_for_chapter,
    generate_screenplay,
)
from app.schema.models import Character, Location, Screenplay

ROOT = Path(__file__).resolve().parents[2]


def fake_openai_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 80, "completion_tokens": 40},
    }


def sample_chapters():
    return split_novel_text(
        (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")
    )


def sample_global_scan() -> GlobalScanResult:
    return GlobalScanResult(
        characters=[
            Character(
                character_id="C001",
                name="林砚",
                aliases=["林队", "砚哥"],
                role="protagonist",
                description="重新调查旧案的刑警。",
            ),
            Character(
                character_id="C002",
                name="周南",
                aliases=[],
                role="supporting",
                description="旧案关键人物。",
            ),
            Character(
                character_id="C003",
                name="陈叔",
                aliases=[],
                role="minor",
                description="档案室管理员。",
            ),
        ],
        locations=[
            Location(
                location_id="L001",
                name="巷口",
                aliases=["老街巷口"],
                description="林砚收到匿名信并与周南对峙的地点。",
            ),
            Location(
                location_id="L002",
                name="档案室",
                aliases=[],
                description="林砚查阅旧案卷宗的地点。",
            ),
        ],
        chapter_summaries={
            "CH001": "林砚在雨夜收到匿名信，旧案出现新的疑点。",
            "CH002": "林砚在档案室发现旧案卷宗存在被涂改的证词。",
            "CH003": "林砚在巷口见到周南，双方围绕旧案发生对峙。",
        },
    )


def scene_response_for(chapter_id: str) -> dict:
    if chapter_id == "CH001":
        return {
            "scenes": [
                {
                    "scene_id": "S001",
                    "title": "雨夜来信",
                    "source": {
                        "chapter": "CH001",
                        "para_range": {"start": 1, "end": 3},
                        "fidelity": "condensed",
                        "quote": "雨从傍晚开始落下",
                    },
                    "heading": {
                        "int_ext": "EXT",
                        "location_id": "L001",
                        "time_of_day": "night",
                    },
                    "characters": ["C001"],
                    "objective": "林砚确认匿名信与旧案有关。",
                    "conflict": "匿名信只给出线索，不给出发信人身份。",
                    "elements": [
                        {
                            "type": "action",
                            "text": "林砚站在巷口路灯下，展开被雨水打湿的信纸。",
                        },
                        {
                            "type": "dialogue",
                            "speaker_id": "C001",
                            "line": "三年前的案子，为什么现在才有人提起？",
                            "mode": "normal",
                        },
                    ],
                    "adaptation_log": [
                        {
                            "change_type": "compress",
                            "reason": "将原文收到匿名信的段落压缩为一个可拍场景。",
                        }
                    ],
                }
            ]
        }

    if chapter_id == "CH002":
        return {
            "scenes": [
                {
                    "scene_id": "S002",
                    "title": "旧案卷宗",
                    "source": {
                        "chapter": "CH002",
                        "para_range": {"start": 1, "end": 3},
                        "fidelity": "faithful",
                        "quote": "档案室的灯坏了一半",
                    },
                    "heading": {
                        "int_ext": "INT",
                        "location_id": "L002",
                        "time_of_day": "night",
                    },
                    "characters": ["C001", "C003"],
                    "objective": "林砚寻找旧案卷宗中的缺口。",
                    "conflict": "陈叔试图回避被涂改的证词。",
                    "elements": [
                        {
                            "type": "action",
                            "text": "林砚翻开旧案卷宗，证词中半个名字被黑笔划去。",
                        },
                        {
                            "type": "dialogue",
                            "speaker_id": "C003",
                            "line": "那页材料，最好别再问。",
                            "mode": "normal",
                        },
                    ],
                    "adaptation_log": [
                        {
                            "change_type": "keep",
                            "reason": "保留卷宗被涂改这一关键情节点。",
                        }
                    ],
                }
            ]
        }

    if chapter_id == "CH003":
        return {
            "scenes": [
                {
                    "scene_id": "S003",
                    "title": "巷口重逢",
                    "source": {
                        "chapter": "CH003",
                        "para_range": {"start": 1, "end": 3},
                        "fidelity": "faithful",
                        "quote": "巷口的路灯亮得很迟",
                    },
                    "heading": {
                        "int_ext": "EXT",
                        "location_id": "L001",
                        "time_of_day": "night",
                    },
                    "characters": ["C001", "C002"],
                    "objective": "林砚逼问周南与旧案的关系。",
                    "conflict": "周南拒绝说明自己为何出现在旧案证词中。",
                    "elements": [
                        {
                            "type": "action",
                            "text": "周南站在巷口阴影里，盯着林砚手中的卷宗复印件。",
                        },
                        {
                            "type": "dialogue",
                            "speaker_id": "C001",
                            "line": "被划掉的名字，是你，对吗？",
                            "mode": "normal",
                        },
                        {
                            "type": "dialogue",
                            "speaker_id": "C002",
                            "line": "你不该重新查这件事。",
                            "mode": "normal",
                        },
                    ],
                    "adaptation_log": [
                        {
                            "change_type": "keep",
                            "reason": "保留巷口对峙作为阶段性冲突高潮。",
                        }
                    ],
                }
            ]
        }

    raise AssertionError(f"Unknown chapter_id: {chapter_id}")


def scene_post_fn(url, payload, headers):
    user_text = payload["messages"][-1]["content"]

    for chapter_id in ("CH001", "CH002", "CH003"):
        if chapter_id in user_text:
            return fake_openai_response(
                json.dumps(scene_response_for(chapter_id), ensure_ascii=False)
            )

    raise AssertionError(f"未匹配到章节：{user_text[:80]}")


def test_generate_screenplay_end_to_end_with_schema_and_linter():
    client = LLMClient(
        base_url="https://example.com/v1",
        model="m",
        api_key="k",
        mode="live",
        post_fn=scene_post_fn,
    )

    result = generate_screenplay(
        client=client,
        chapters=sample_chapters(),
        global_scan=sample_global_scan(),
        title="雨夜旧案",
        logline="一封匿名信迫使刑警重新面对三年前的失踪案。",
    )

    assert isinstance(result.screenplay, Screenplay)
    assert result.screenplay.title == "雨夜旧案"
    assert len(result.screenplay.chapters) == 3
    assert len(result.screenplay.scenes) == 3
    assert result.screenplay.scenes[0].estimated_seconds is not None

    assert result.metrics.chapter_count == 3
    assert result.metrics.scene_count == 3
    assert result.metrics.first_pass_schema_ok is True
    assert result.metrics.final_schema_ok is True
    assert result.metrics.schema_repair_attempts == 0
    assert result.metrics.json_repair_attempts == 0
    assert result.metrics.lint_error_count == 0
    assert client.usage.calls == 3


def test_chapter_scene_generation_retries_once_on_bad_json():
    chapters = sample_chapters()
    calls = {"n": 0}

    def post_fn(url, payload, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return fake_openai_response("不是 JSON")
        return fake_openai_response(
            json.dumps(scene_response_for("CH001"), ensure_ascii=False)
        )

    client = LLMClient(
        base_url="https://example.com/v1",
        model="m",
        api_key="k",
        mode="live",
        post_fn=post_fn,
    )

    scenes, repair_attempts = generate_scenes_for_chapter(
        client=client,
        chapter=chapters[0],
        global_scan=sample_global_scan(),
    )

    assert repair_attempts == 1
    assert calls["n"] == 2
    assert scenes[0]["scene_id"] == "S001"


def test_chapter_scene_generation_strips_markdown_code_fence():
    chapters = sample_chapters()
    fenced = "```json\n" + json.dumps(scene_response_for("CH001"), ensure_ascii=False) + "\n```"

    client = LLMClient(
        base_url="https://example.com/v1",
        model="m",
        api_key="k",
        mode="live",
        post_fn=lambda url, payload, headers: fake_openai_response(fenced),
    )

    scenes, repair_attempts = generate_scenes_for_chapter(
        client=client,
        chapter=chapters[0],
        global_scan=sample_global_scan(),
    )

    assert repair_attempts == 0
    assert scenes[0]["title"] == "雨夜来信"


def test_schema_validation_failure_triggers_repair_once():
    chapters = sample_chapters()[:1]
    calls = {"n": 0}

    invalid = scene_response_for("CH001")
    invalid["scenes"][0]["elements"][1]["speaker_id"] = "C999"

    valid = scene_response_for("CH001")

    def post_fn(url, payload, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return fake_openai_response(json.dumps(invalid, ensure_ascii=False))

        # 第二次调用应来自 schema repair prompt，返回修复后的 scenes。
        assert "schema_error" in payload["messages"][-1]["content"]
        return fake_openai_response(json.dumps(valid, ensure_ascii=False))

    client = LLMClient(
        base_url="https://example.com/v1",
        model="m",
        api_key="k",
        mode="live",
        post_fn=post_fn,
    )

    result = generate_screenplay(
        client=client,
        chapters=chapters,
        global_scan=sample_global_scan(),
        title="修复测试",
    )

    assert calls["n"] == 2
    assert result.metrics.first_pass_schema_ok is False
    assert result.metrics.schema_repair_attempts == 1
    assert result.metrics.final_schema_ok is True
    assert result.screenplay.scenes[0].elements[1].speaker_id == "C001"


def test_schema_validation_failure_without_repair_raises():
    chapters = sample_chapters()[:1]

    invalid = scene_response_for("CH001")
    invalid["scenes"][0]["heading"]["location_id"] = "L999"

    client = LLMClient(
        base_url="https://example.com/v1",
        model="m",
        api_key="k",
        mode="live",
        post_fn=lambda url, payload, headers: fake_openai_response(
            json.dumps(invalid, ensure_ascii=False)
        ),
    )

    with pytest.raises(SceneGenerationError):
        generate_screenplay(
            client=client,
            chapters=chapters,
            global_scan=sample_global_scan(),
            title="失败测试",
            max_schema_repair_attempts=0,
        )


def test_record_then_replay_scene_generation(tmp_path):
    chapters = sample_chapters()[:1]

    recorder = LLMClient(
        base_url="https://example.com/v1",
        model="m",
        api_key="k",
        mode="record",
        recordings_dir=tmp_path,
        post_fn=lambda url, payload, headers: fake_openai_response(
            json.dumps(scene_response_for("CH001"), ensure_ascii=False)
        ),
    )

    first = generate_screenplay(
        client=recorder,
        chapters=chapters,
        global_scan=sample_global_scan(),
        title="录制测试",
    )

    replayer = LLMClient(mode="replay", recordings_dir=tmp_path)
    second = generate_screenplay(
        client=replayer,
        chapters=chapters,
        global_scan=sample_global_scan(),
        title="录制测试",
    )

    assert len(list(tmp_path.glob("*.json"))) == 1
    assert second.screenplay.scenes[0].title == first.screenplay.scenes[0].title
    assert second.metrics.final_schema_ok is True
