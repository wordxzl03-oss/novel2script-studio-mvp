import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes import get_llm_client
from app.llm.client import LLMClient
from app.main import app


ROOT = Path(__file__).resolve().parents[2]


def fake_openai_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


def global_scan_response(chapter_marker: str) -> dict:
    if "CH001" in chapter_marker or "第1章" in chapter_marker:
        return {
            "characters": [
                {
                    "name": "林砚",
                    "aliases": ["砚哥"],
                    "role": "protagonist",
                    "description": "重新调查旧案的刑警。",
                }
            ],
            "locations": [
                {
                    "name": "巷口",
                    "aliases": ["老街巷口"],
                    "description": "匿名信出现的地点。",
                }
            ],
            "summary": "林砚在雨夜收到匿名信，旧案出现新的疑点。",
        }

    if "CH002" in chapter_marker or "第2章" in chapter_marker:
        return {
            "characters": [
                {
                    "name": "林队",
                    "aliases": ["林砚"],
                    "role": "protagonist",
                    "description": "重新调查旧案的刑警。",
                },
                {
                    "name": "陈叔",
                    "aliases": [],
                    "role": "minor",
                    "description": "档案室管理员。",
                },
            ],
            "locations": [
                {
                    "name": "档案室",
                    "aliases": [],
                    "description": "存放旧案卷宗的地点。",
                }
            ],
            "summary": "林砚在档案室发现旧案卷宗存在被涂改的证词。",
        }

    if "CH003" in chapter_marker or "第3章" in chapter_marker:
        return {
            "characters": [
                {
                    "name": "周南",
                    "aliases": [],
                    "role": "supporting",
                    "description": "旧案关键人物。",
                }
            ],
            "locations": [
                {
                    "name": "巷口",
                    "aliases": ["老街巷口"],
                    "description": "林砚与周南对峙的地点。",
                }
            ],
            "summary": "林砚在巷口见到周南，双方围绕旧案发生对峙。",
        }

    raise AssertionError(f"无法匹配全局扫描章节：{chapter_marker[:120]}")


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
                            "reason": "将收到匿名信的段落压缩为一个可拍场景。",
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

    raise AssertionError(f"无法匹配场景生成章节：{chapter_id}")


def api_post_fn(url, payload, headers):
    user_text = payload["messages"][-1]["content"]

    # scene generation / schema repair prompts contain the registry field
    if '"registry"' in user_text:
        for chapter_id in ("CH001", "CH002", "CH003"):
            if chapter_id in user_text:
                return fake_openai_response(
                    json.dumps(scene_response_for(chapter_id), ensure_ascii=False)
                )

    # global scan prompts contain chapter markers but not scene-generation registry
    for chapter_id in ("CH001", "CH002", "CH003"):
        if chapter_id in user_text:
            return fake_openai_response(
                json.dumps(global_scan_response(chapter_id), ensure_ascii=False)
            )

    # fallback for tests where prompt contains original title text
    for marker in ("第1章", "第2章", "第3章"):
        if marker in user_text:
            return fake_openai_response(
                json.dumps(global_scan_response(marker), ensure_ascii=False)
            )

    raise AssertionError(f"未匹配到 API 测试请求：{user_text[:160]}")


def make_test_client() -> TestClient:
    fake_client = LLMClient(
        base_url="https://example.com/v1",
        model="mock-model",
        mode="live",
        post_fn=api_post_fn,
    )

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_health_check():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_api_runs_full_pipeline():
    client = make_test_client()
    novel_text = (ROOT / "examples" / "sample_novel.txt").read_text(encoding="utf-8")

    response = client.post(
        "/api/generate",
        json={
            "novel_text": novel_text,
            "title": "雨夜旧案",
            "logline": "一封匿名信迫使刑警重新面对三年前的失踪案。",
            "profile": "film",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["screenplay"]["title"] == "雨夜旧案"
    assert len(data["screenplay"]["chapters"]) == 3
    assert len(data["screenplay"]["scenes"]) == 3

    assert "global_scan" in data
    assert len(data["global_scan"]["characters"]) >= 3
    assert len(data["global_scan"]["locations"]) >= 2

    assert "lint_findings" in data
    assert "metrics" in data
    assert data["metrics"]["chapter_count"] == 3
    assert data["metrics"]["scene_count"] == 3
    assert data["metrics"]["final_schema_ok"] is True


def test_generate_api_rejects_too_short_text():
    client = make_test_client()

    response = client.post(
        "/api/generate",
        json={
            "novel_text": "第一章 太短\n只有一章。",
            "title": "失败用例",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "error" in body["detail"]