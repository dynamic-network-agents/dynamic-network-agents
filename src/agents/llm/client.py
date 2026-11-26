"""LLM 客户端：OpenAI 兼容的 chat/completions 调用 + 重试 + 调用账本。

网关地址来自 `configs/llm.yaml`（`base_url`，默认 `:10110/v1`），**密钥不落代码**
——按赛题约定走 eval 代理，鉴权由网关侧处理（`LLM_API_KEY` 在容器 env 里）。

**为什么自己写而不用 openai SDK**：赛题要求"小参数量 + 低比特量化"模型，且网关是
LiteLLM 的 OpenAI 兼容端点；直接用 `requests` 打 HTTP 更可控（超时、重试、计量都能
自己记账），也少一个依赖。

**重试策略**：只对**可重试错误**重试（连接失败、5xx、429），指数退避；
4xx 业务错误（如模型名不存在）**不重试**——重试只是浪费预算。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger("agents.llm.client")


@dataclass
class LLMConfig:
    """LLM 连接与生成参数（对应 `configs/llm.yaml`）。"""

    enabled: bool = False
    base_url: str = "http://localhost:10110/v1"
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout_s: float = 60.0
    max_retries: int = 2
    retry_backoff_s: float = 1.0

    @classmethod
    def from_settings(cls, llm: dict[str, Any]) -> "LLMConfig":
        """从 `configs/llm.yaml` 的字典构造（缺省项取类默认值）。"""
        return cls(
            enabled=bool(llm.get("enabled", False)),
            base_url=llm.get("base_url", cls.base_url),
            model=llm.get("model", ""),
            temperature=float(llm.get("temperature", cls.temperature)),
            max_tokens=int(llm.get("max_tokens", cls.max_tokens)),
            timeout_s=float(llm.get("timeout_s", cls.timeout_s)),
            max_retries=int(llm.get("max_retries", cls.max_retries)),
        )


@dataclass
class LLMCall:
    """一次调用的记录（进入调用账本）。"""

    purpose: str
    ok: bool
    elapsed_s: float
    attempts: int
    prompt_chars: int
    completion_chars: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "purpose": self.purpose,
            "ok": self.ok,
            "elapsed_s": round(self.elapsed_s, 6),
            "attempts": self.attempts,
            "prompt_chars": self.prompt_chars,
            "completion_chars": self.completion_chars,
            "error": self.error,
        }


@dataclass
class CallLedger:
    """调用账本：次数、成功率、总耗时（实验分析用）。"""

    calls: list[LLMCall] = field(default_factory=list)

    def record(self, call: LLMCall) -> None:
        self.calls.append(call)

    @property
    def total(self) -> int:
        return len(self.calls)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.calls if not c.ok)

    @property
    def total_elapsed_s(self) -> float:
        return sum(c.elapsed_s for c in self.calls)

    def by_purpose(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for call in self.calls:
            out[call.purpose] = out.get(call.purpose, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "failed": self.failed,
            "total_elapsed_s": round(self.total_elapsed_s, 6),
            "by_purpose": self.by_purpose(),
        }


class LLMClient:
    """大模型网关客户端（OpenAI 兼容 chat/completions）。"""

    def __init__(self, config: LLMConfig, *, session: requests.Session | None = None):
        self.config = config
        self._session = session or requests.Session()
        self.ledger = CallLedger()

    @property
    def enabled(self) -> bool:
        """是否启用（`configs/llm.yaml` 的 `enabled`）。关掉时 `complete()` 直接返回空串。"""
        return self.config.enabled and bool(self.config.model)

    def complete(self, prompt: str, *, system: str = "", purpose: str = "") -> str:
        """发一次对话补全，返回文本；失败返回空串（不抛异常——LLM 失败不该拖垮闭环）。

        `purpose` 用于调用账本分类（如 "priority_hint" / "diagnosis" / "explanation"）。
        """
        if not self.enabled:
            return ""
        started = time.monotonic()
        attempts = 0
        last_error = ""
        while attempts <= self.config.max_retries:
            attempts += 1
            try:
                text = self._request(prompt, system)
                self.ledger.record(LLMCall(
                    purpose=purpose, ok=True,
                    elapsed_s=time.monotonic() - started,
                    attempts=attempts, prompt_chars=len(prompt),
                    completion_chars=len(text),
                ))
                return text
            except _RetryableError as e:
                last_error = str(e)
                if attempts > self.config.max_retries:
                    break
                backoff = self.config.retry_backoff_s * (2 ** (attempts - 1))
                log.warning("LLM 调用失败（可重试）：%s，%.1fs 后第 %d 次重试", e, backoff, attempts + 1)
                time.sleep(backoff)
            except Exception as e:  # noqa: BLE001 —— 不可重试错误直接记账返回
                last_error = str(e)
                break
        self.ledger.record(LLMCall(
            purpose=purpose, ok=False,
            elapsed_s=time.monotonic() - started,
            attempts=attempts, prompt_chars=len(prompt), error=last_error,
        ))
        log.warning("LLM 调用最终失败（purpose=%s）：%s", purpose, last_error)
        return ""

    def complete_json(self, prompt: str, *, system: str = "", purpose: str = "") -> dict | None:
        """要求模型返回 JSON；解析失败返回 None（调用方走确定性兜底路径）。"""
        text = self.complete(prompt, system=system, purpose=purpose)
        if not text:
            return None
        return parse_json_object(text)

    def _request(self, prompt: str, system: str) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        try:
            response = self._session.post(
                url, json=payload, timeout=self.config.timeout_s,
            )
        except requests.RequestException as e:
            raise _RetryableError(f"连接失败: {e}") from e
        if response.status_code >= 500 or response.status_code == 429:
            raise _RetryableError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("响应无 choices")
        return choices[0].get("message", {}).get("content", "") or ""


class _RetryableError(Exception):
    """可重试的错误（连接失败、5xx、429）。"""


def parse_json_object(text: str) -> dict | None:
    """从模型输出里抠出 JSON 对象。

    小模型常在 JSON 外面裹 ```json 围栏或加解释文字，这里做容错：
    先直接解析，失败则找第一个 `{` 到最后一个 `}` 的片段再试。
    """
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
