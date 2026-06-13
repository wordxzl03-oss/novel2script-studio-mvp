from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes import get_llm_client
from app.llm.client import LLMClient, LLMError
from app.main import app


ROOT = Path(__file__).resolve().parents[2]


def clear_llm_env(monkeypatch):
    for name in (
        "DEMO_MODE",
        "LLM_MODE",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "RATE_LIMIT_PER_DAY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_env_example_documents_server_side_llm_config():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for name in (
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "DEMO_MODE",
        "RATE_LIMIT_PER_DAY",
    ):
        assert name in env_example

    assert "server" in env_example.lower()


def test_demo_mode_does_not_require_api_key(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("DEMO_MODE", "1")

    client = get_llm_client()

    assert isinstance(client, LLMClient)
    assert client.mode == "replay"
    assert client.api_key == ""


def test_live_mode_requires_api_key_base_url_and_model(monkeypatch):
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "model")

    with pytest.raises(HTTPException) as exc_info:
        get_llm_client()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "llm_configuration_error"
    assert exc_info.value.detail["missing"] == ["LLM_API_KEY"]


def test_llm_client_live_mode_requires_api_key():
    client = LLMClient(
        base_url="https://example.com/v1",
        model="model",
        api_key="",
        mode="live",
        post_fn=lambda url, payload, headers: {"choices": [{"message": {"content": "{}"}}]},
    )

    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hello"}], temperature=0.0)


def test_generate_rate_limit_returns_structured_error():
    from app.api.routes import get_rate_limiter
    from app.core.rate_limit import InMemoryRateLimiter

    app.dependency_overrides[get_llm_client] = lambda: LLMClient(
        base_url="https://example.com/v1",
        model="model",
        api_key="test-key",
        mode="live",
        post_fn=lambda url, payload, headers: {"choices": [{"message": {"content": "{}"}}]},
    )
    app.dependency_overrides[get_rate_limiter] = lambda: InMemoryRateLimiter(limit_per_day=0)

    try:
        response = TestClient(app).post(
            "/api/generate",
            json={"novel_text": "第1章 开始\n这是一段用于触发限频的文本。", "title": "限频测试"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == {
        "error": "rate_limit_exceeded",
        "message": "Daily live LLM call limit exceeded.",
        "limit": 0,
        "remaining": 0,
    }


def test_frontend_does_not_contain_llm_api_key_string():
    frontend_dir = ROOT / "frontend"
    if not frontend_dir.exists():
        return

    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in frontend_dir.rglob("*")
        if path.is_file() and "node_modules" not in path.parts
    )

    assert "LLM_API_KEY" not in text
    assert "sk-" not in text
