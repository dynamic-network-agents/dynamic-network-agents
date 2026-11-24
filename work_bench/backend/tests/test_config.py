"""work_bench 后端单元测试：配置与令牌解析（不依赖 FastAPI / 仿真器）。"""
from __future__ import annotations

import json

from backend import config


def _gateway(tmp_path, *, ctrl="ctrl-tok", opens=("open-1", "open-2")):
    p = tmp_path / "gateway.json"
    data = {"ctrlToken": ctrl, "openTokens": list(opens)}
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_derive_ctrl_base():
    assert config.derive_ctrl_base("http://h:10100/api/open/v1") == "http://h:10100/api/ctrl/v1"
    assert config.derive_ctrl_base("http://h:10100/api/open/v1/") == "http://h:10100/api/ctrl/v1"
    # 识别不了前缀就不猜
    assert config.derive_ctrl_base("http://h:10000/sdn-api/open/v1") == ""
    assert config.derive_ctrl_base("") == ""


def test_ctrl_mode_prefers_ctrl_token_from_env():
    creds = config.resolve_credentials(auth_mode="ctrl", ctrl_token="A", token="B", token_file="")
    assert (creds.token, creds.auth_mode, creds.source) == ("A", "ctrl", "env:SIM_CTRL_TOKEN")
    assert creds.header_name == "X-Ctrl-Token"


def test_ctrl_mode_reads_ctrl_token_from_gateway_file(tmp_path):
    creds = config.resolve_credentials(
        auth_mode="ctrl", ctrl_token="", token="", token_file=_gateway(tmp_path)
    )
    assert creds.token == "ctrl-tok"
    assert creds.source == "file:ctrlToken"
    assert creds.header_name == "X-Ctrl-Token"


def test_ctrl_mode_never_silently_falls_back_to_open_token(tmp_path):
    """只有 openTokens 时保持 ctrl 模式且 token 为空——宁可报错也不要污染 agent 统计。"""
    creds = config.resolve_credentials(
        auth_mode="ctrl",
        ctrl_token="",
        token="",
        token_file=_gateway(tmp_path, ctrl=""),
    )
    assert creds.token == ""
    assert creds.auth_mode == "ctrl"
    assert creds.source == "none"


def test_open_mode_is_explicit_opt_in(tmp_path):
    creds = config.resolve_credentials(
        auth_mode="open", token="", ctrl_token="", token_file=_gateway(tmp_path)
    )
    assert (creds.token, creds.auth_mode) == ("open-1", "open")
    assert creds.header_name == "X-Open-Token"


def test_invalid_auth_mode_defaults_to_ctrl():
    creds = config.resolve_credentials(auth_mode="whatever", ctrl_token="X", token_file="")
    assert creds.auth_mode == "ctrl"


def test_credentials_repr_hides_token():
    creds = config.Credentials("super-secret", "ctrl", "env:SIM_CTRL_TOKEN")
    assert "super-secret" not in repr(creds)
    assert "***" in repr(creds)


def test_svcmeta_only_on_ctrl_channel():
    assert config.svcmeta_allowed("ctrl", True) is True
    assert config.svcmeta_allowed("ctrl", False) is False
    # open 令牌调控制面会被 1006 拒绝，且请求会写进 agent 统计，必须关掉
    assert config.svcmeta_allowed("open", True) is False
