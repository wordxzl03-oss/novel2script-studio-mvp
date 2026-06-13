from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx


class LLMError(RuntimeError):
    """LLM 调用相关错误的基类。"""


class RecordingMissingError(LLMError):
    """回放模式下缺少对应录制文件。"""


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def add(self, usage: dict | None) -> None:
        if usage:
            self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
            self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.calls += 1


class LLMClient:
    """统一 LLM 客户端：OpenAI 风格接口 + 录制/回放。

    模式（环境变量 LLM_MODE；DEMO_MODE=1 等价于 replay）：
    - live   直连 API；
    - record 直连 API，并把请求/响应写入 recordings_dir（生成演示素材）；
    - replay 只读 recordings_dir，不发任何网络请求（评委无 Key 复现、单元测试）。

    录制文件按"messages + temperature"的哈希命名，刻意不含 model 名，
    这样评委在没有配置任何模型的环境下也能回放。
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        mode: str | None = None,
        recordings_dir: str | Path | None = None,
        timeout: float = 120.0,
        post_fn: Callable[[str, dict, dict], dict] | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else os.getenv("LLM_BASE_URL", "")).rstrip(
            "/"
        )
        self.model = model if model is not None else os.getenv("LLM_MODEL", "")
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")

        if mode is None:
            mode = "replay" if os.getenv("DEMO_MODE") == "1" else os.getenv("LLM_MODE", "live")
        if mode not in {"live", "record", "replay"}:
            raise LLMError(f"未知的 LLM_MODE: {mode!r}（应为 live / record / replay）")
        self.mode = mode

        default_dir = Path(__file__).resolve().parents[3] / "examples" / "llm_recordings"
        self.recordings_dir = Path(
            recordings_dir or os.getenv("LLM_RECORDINGS_DIR") or default_dir
        )
        self.timeout = timeout
        self.usage = LLMUsage()
        self._post_fn = post_fn  # 测试注入点：替代真实 HTTP 调用

    # ---------------------------------------------------------------- key

    def request_key(self, messages: list[dict], temperature: float) -> str:
        payload = json.dumps(
            {"messages": messages, "temperature": temperature},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    # --------------------------------------------------------------- chat

    def chat(self, messages: list[dict], *, temperature: float = 0.2) -> str:
        key = self.request_key(messages, temperature)
        path = self.recordings_dir / f"{key}.json"

        if self.mode == "replay":
            if not path.exists():
                raise RecordingMissingError(
                    f"回放模式缺少录制文件 {path.name}。"
                    f"请先在配置好 API Key 的环境中用 LLM_MODE=record 跑一遍流水线生成录制。"
                )
            data = json.loads(path.read_text(encoding="utf-8"))
            return data["response"]["content"]

        content, usage = self._call_api(messages, temperature)
        self.usage.add(usage)

        if self.mode == "record":
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                        },
                        "response": {"content": content, "usage": usage},
                        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return content

    # ----------------------------------------------------------- internal

    def _missing_live_config(self) -> list[str]:
        missing = []
        if not self.api_key:
            missing.append("LLM_API_KEY")
        if not self.base_url:
            missing.append("LLM_BASE_URL")
        if not self.model:
            missing.append("LLM_MODEL")
        return missing

    def _call_api(self, messages: list[dict], temperature: float) -> tuple[str, dict | None]:
        missing = self._missing_live_config()
        if missing:
            raise LLMError(
                "Missing server-side LLM configuration: " + ", ".join(missing)
            )

        if not self.base_url or not self.model:
            raise LLMError(
                "缺少 LLM_BASE_URL / LLM_MODEL 配置（live / record 模式需要直连 API；"
                "无 Key 演示请使用 DEMO_MODE=1）。"
            )
        url = f"{self.base_url}/chat/completions"
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self._post_fn is not None:
            data: dict[str, Any] = self._post_fn(url, payload, headers)
        else:
            response = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"API 响应格式异常：{data!r}") from exc
        return content, data.get("usage")
