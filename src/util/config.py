"""配置加载与令牌读取。

令牌不入代码：从 simulator/conf/gateway.json 运行时读取，勿打印到日志或提交。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

# src/util/config.py -> 项目根目录（上溯两级）
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def load_settings() -> dict[str, dict[str, Any]]:
    """加载 configs/*.yaml，返回以文件名为 key 的嵌套字典。

    键：app / simulator / qos / llm。
    """
    settings: dict[str, dict[str, Any]] = {}
    for name in ("app", "simulator", "qos", "llm"):
        p = CONFIG_DIR / f"{name}.yaml"
        if p.exists():
            settings[name] = _read_yaml(p)
    return settings


def _resolve(repo_root: Path, path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else repo_root / p


def load_tokens(token_file: str | None = None) -> dict[str, Any]:
    """从 simulator/conf/gateway.json 读令牌。

    返回 dict：
        open_tokens: list[str]  公开令牌（用于 X-Open-Token）
        ctrl_token: str|None    控制令牌（用于 X-Ctrl-Token，仅内部接口）

    注：gateway.json 的 `extraLinkIds` 是并行链路 labKey→linkId 的稳定 ID 映射，
    不是"业务要剔除的链路"，智能体构图无需关心；此处不返回。
    """
    path = _resolve(REPO_ROOT, token_file) if token_file else REPO_ROOT / "simulator" / "conf" / "gateway.json"
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {
        "open_tokens": raw.get("openTokens", []),
        "ctrl_token": raw.get("ctrlToken"),
    }


def load_open_token(token_file: str | None = None) -> str:
    """返回第一个公开令牌；无令牌时抛错（不静默降级）。"""
    tokens = load_tokens(token_file)["open_tokens"]
    if not tokens:
        raise RuntimeError("gateway.json 中无 openTokens，无法连接仿真器")
    return tokens[0]
