"""LLM 通道单测（`agents/llm/`）：配置、调用、重试、账本、JSON 解析。"""
import json

import requests

from agents.llm.client import CallLedger, LLMClient, LLMConfig, parse_json_object
from agents.llm.prompts import render, render_json_context


class FakeResponse:
    """最小 HTTP 响应替身。"""

    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """按序返回预设响应；记录请求。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def post(self, url, json=None, timeout=None):
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _ok(text="hello"):
    return FakeResponse(200, {"choices": [{"message": {"content": text}}]})


def _config(**kw):
    base = dict(enabled=True, base_url="http://gw/v1", model="m", timeout_s=1.0,
                max_retries=2, retry_backoff_s=0.0)
    base.update(kw)
    return LLMConfig(**base)


# --------------------------------------------------------------------------- 配置
def test_config_from_settings_reads_yaml_shape():
    cfg = LLMConfig.from_settings({
        "enabled": True, "base_url": "http://x/v1", "model": "m",
        "temperature": 0.3, "max_tokens": 512,
    })
    assert cfg.enabled is True
    assert cfg.model == "m"
    assert cfg.temperature == 0.3
    assert cfg.max_tokens == 512


def test_disabled_client_short_circuits():
    client = LLMClient(_config(enabled=False))
    assert client.enabled is False
    assert client.complete("hi") == ""
    assert client.ledger.total == 0        # 禁用时不产生调用记录


def test_client_disabled_without_model():
    assert LLMClient(_config(model="")).enabled is False


# --------------------------------------------------------------------------- 调用
def test_complete_returns_content_and_records_call():
    session = FakeSession([_ok("结果")])
    client = LLMClient(_config(), session=session)
    assert client.complete("问", purpose="priority_hint") == "结果"
    assert client.ledger.total == 1
    assert client.ledger.calls[0].ok is True
    assert client.ledger.calls[0].purpose == "priority_hint"
    assert session.requests[0]["url"] == "http://gw/v1/chat/completions"


def test_complete_sends_system_message_when_given():
    session = FakeSession([_ok()])
    client = LLMClient(_config(), session=session)
    client.complete("问", system="你是运维智能体")
    messages = session.requests[0]["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_retry_on_5xx_then_success():
    session = FakeSession([FakeResponse(503, text="busy"), _ok("好")])
    client = LLMClient(_config(), session=session)
    assert client.complete("问") == "好"
    assert client.ledger.calls[0].attempts == 2
    assert client.ledger.calls[0].ok is True


def test_retry_on_connection_error_then_success():
    session = FakeSession([requests.ConnectionError("refused"), _ok("好")])
    client = LLMClient(_config(), session=session)
    assert client.complete("问") == "好"
    assert client.ledger.calls[0].attempts == 2


def test_no_retry_on_4xx():
    session = FakeSession([FakeResponse(400, text="bad model")])
    client = LLMClient(_config(), session=session)
    assert client.complete("问") == ""
    assert client.ledger.total == 1
    assert client.ledger.calls[0].attempts == 1      # 4xx 不重试
    assert client.ledger.calls[0].ok is False
    assert client.ledger.failed == 1


def test_gives_up_after_max_retries():
    session = FakeSession([FakeResponse(500, text="x"), FakeResponse(500, text="x"),
                            FakeResponse(500, text="x")])
    client = LLMClient(_config(max_retries=2), session=session)
    assert client.complete("问") == ""
    assert client.ledger.calls[0].attempts == 3      # 首次 + 2 次重试
    assert client.ledger.calls[0].ok is False


# --------------------------------------------------------------------------- 账本
def test_ledger_summarizes_by_purpose():
    ledger = CallLedger()
    session = FakeSession([_ok(), _ok(), FakeResponse(400, text="e")])
    client = LLMClient(_config(), session=session)
    client.complete("a", purpose="diagnosis")
    client.complete("b", purpose="diagnosis")
    client.complete("c", purpose="explanation")
    assert client.ledger.by_purpose() == {"diagnosis": 2, "explanation": 1}
    assert client.ledger.total == 3
    assert client.ledger.failed == 1


# --------------------------------------------------------------------------- JSON 解析
def test_complete_json_parses_plain_object():
    session = FakeSession([_ok('{"a": 1}')])
    client = LLMClient(_config(), session=session)
    assert client.complete_json("问") == {"a": 1}


def test_complete_json_tolerates_code_fence():
    session = FakeSession([_ok('```json\n{"a": 1}\n```')])
    client = LLMClient(_config(), session=session)
    assert client.complete_json("问") == {"a": 1}


def test_complete_json_tolerates_surrounding_prose():
    session = FakeSession([_ok('好的，结论如下：{"cause": "断链"} 以上。')])
    client = LLMClient(_config(), session=session)
    assert client.complete_json("问") == {"cause": "断链"}


def test_complete_json_returns_none_on_garbage():
    session = FakeSession([_ok("完全不是 JSON")])
    client = LLMClient(_config(), session=session)
    assert client.complete_json("问") is None


def test_parse_json_object_rejects_non_object():
    assert parse_json_object("[1, 2]") is None


# --------------------------------------------------------------------------- 提示词
def test_render_fills_placeholders_and_tolerates_missing():
    assert render("a={x} b={y}", x="1") == "a=1 b="


def test_render_json_context_truncates():
    payload = {"k": "v" * 5000}
    out = render_json_context(payload, max_chars=100)
    assert len(out) < 200
    assert out.endswith("...(truncated)")


def test_render_json_context_is_compact_json():
    assert json.loads(render_json_context({"a": 1})) == {"a": 1}
