import json

import pytest

from app.llm.client import LLMClient, LLMError, RecordingMissingError


def fake_openai_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_record_then_replay_round_trip(tmp_path):
    messages = [{"role": "user", "content": "你好"}]

    recorder = LLMClient(
        base_url="https://example.com/v1", model="test-model",
        api_key="k", mode="record", recordings_dir=tmp_path,
        post_fn=lambda url, payload, headers: fake_openai_response("回答内容"),
    )
    assert recorder.chat(messages, temperature=0.0) == "回答内容"
    assert len(list(tmp_path.glob("*.json"))) == 1

    # 回放端不配置任何模型/Key，模拟评委环境
    replayer = LLMClient(mode="replay", recordings_dir=tmp_path)
    assert replayer.chat(messages, temperature=0.0) == "回答内容"
    assert replayer.usage.calls == 1
    assert replayer.usage.prompt_tokens == 10


def test_replay_missing_recording_raises_helpful_error(tmp_path):
    client = LLMClient(mode="replay", recordings_dir=tmp_path)
    with pytest.raises(RecordingMissingError):
        client.chat([{"role": "user", "content": "没有录制"}], temperature=0.0)


def test_request_key_excludes_model_for_portable_replay(tmp_path):
    messages = [{"role": "user", "content": "同样的请求"}]
    a = LLMClient(model="model-a", mode="replay", recordings_dir=tmp_path)
    b = LLMClient(model="model-b", mode="replay", recordings_dir=tmp_path)
    assert a.request_key(messages, 0.0) == b.request_key(messages, 0.0)


def test_live_mode_without_config_raises():
    client = LLMClient(base_url="", model="", mode="live")
    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])


def test_malformed_api_response_raises(tmp_path):
    client = LLMClient(
        base_url="https://example.com/v1", model="m", mode="live",
        post_fn=lambda url, payload, headers: {"unexpected": True},
    )
    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])
