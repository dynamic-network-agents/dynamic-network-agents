"""work_bench 后端配置：只从环境变量 / .env 读取，Token 绝不下发前端、不进日志。

观测通道默认走「仿真器前端同款」的 ctrl 令牌（`X-Ctrl-Token`）：
调用语义与公开 API 完全一致，但请求落 `llm_gateway_front_stat.log`，
不会写进 `llm_gateway_call_stat.log`（即 `GET /api/ctrl/v1/agent-calls` 读的 agent 统计台账）。
只有显式置 `SIM_AUTH=open` 才会回到公开令牌通道，届时调用会污染 agent 统计。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent

OPEN_PREFIX = "/api/open/v1"
CTRL_PREFIX = "/api/ctrl/v1"
DEFAULT_BASE_URL = "http://127.0.0.1:10100" + OPEN_PREFIX

AUTH_CTRL = "ctrl"
AUTH_OPEN = "open"
_AUTH_MODES = (AUTH_CTRL, AUTH_OPEN)


def _load_dotenv(path: Path | None = None) -> None:
    """极简 .env 加载（KEY=VALUE，忽略空行/注释），不覆盖已存在的环境变量。"""
    p = path or (_BASE_DIR / ".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _bool(name: str, default: bool) -> bool:
    """宽松布尔解析：1/true/yes/on 为真，0/false/no/off 为假，空值/未知取默认。"""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def derive_ctrl_base(open_base: str) -> str:
    """公开 API 基址 → 控制面 API 基址；识别不了前缀时返回空串（不猜）。"""
    base = (open_base or "").strip().rstrip("/")
    if base.endswith(OPEN_PREFIX):
        return base[: -len(OPEN_PREFIX)] + CTRL_PREFIX
    return ""


_load_dotenv()

SIM_BASE_URL = os.environ.get("SIM_BASE_URL", DEFAULT_BASE_URL)
SIM_AUTH = (os.environ.get("SIM_AUTH", AUTH_CTRL) or AUTH_CTRL).strip().lower()
if SIM_AUTH not in _AUTH_MODES:
    SIM_AUTH = AUTH_CTRL

SIM_TOKEN = os.environ.get("SIM_TOKEN", "")            # 兼容旧配置：含义随 SIM_AUTH
SIM_CTRL_TOKEN = os.environ.get("SIM_CTRL_TOKEN", "")
SIM_TOKEN_FILE = os.environ.get("SIM_TOKEN_FILE", "")

SIM_CTRL_BASE_URL = os.environ.get("SIM_CTRL_BASE_URL", "") or derive_ctrl_base(SIM_BASE_URL)

AGENT_ID = os.environ.get("WORKBENCH_AGENT_ID", "workbench")
TIMEOUT_S = float(os.environ.get("SIM_TIMEOUT_S", "6"))
DETAIL_WORKERS = int(os.environ.get("SIM_DETAIL_WORKERS", "8"))
DETAIL_TTL_S = float(os.environ.get("SIM_DETAIL_TTL_S", "4"))

# 业务分类优先取仿真器实时 svc-meta（/api/ctrl/v1/svc-meta），失败再退回离线 bg-service.json
SVCMETA_ENABLED = _bool("WORKBENCH_SVCMETA", True)
# 正式录分时建议置 0：改路径会被仿真器记成 source=agent 的 path 事件，无法用令牌隔离
ALLOW_REPATH = _bool("WORKBENCH_ALLOW_REPATH", True)

# 数据健康：超过该秒数未刷新即标 STALE（默认 3× 前端 2s 轮询）
STALE_AFTER_S = float(os.environ.get("WORKBENCH_STALE_AFTER_S", "6"))
# 离线模式：只读离线场景文件（net-topo.json + bg-service.json），不连仿真器
OFFLINE_MODE = _bool("WORKBENCH_OFFLINE", False)
NET_TOPO_PATH = os.environ.get("NET_TOPO_PATH", "")

# 分页读取：仿真器 page/size，默认 500、上限 2000；页数上限用于防御异常
PAGE_SIZE = int(os.environ.get("WORKBENCH_PAGE_SIZE", "500"))
MAX_PAGES = int(os.environ.get("WORKBENCH_MAX_PAGES", "20"))

BG_SERVICE_PATH = os.environ.get("BG_SERVICE_PATH", "")
SERVICE_PATHS_PATH = os.environ.get("SERVICE_PATHS_PATH", "")

HOST = os.environ.get("WORKBENCH_HOST", "127.0.0.1")
PORT = int(os.environ.get("WORKBENCH_PORT", "8000"))

# 前端静态目录：默认 work_bench/frontend/dist，存在则后端一并托管（同源单进程部署，免 CORS、免 Node）
STATIC_DIR = os.environ.get("WORKBENCH_STATIC_DIR", str(_BASE_DIR.parent / "frontend" / "dist"))
# CORS 白名单（逗号分隔）：仅 dev 模式（vite :5173）跨域需要；同源托管时虽无跨域但也无碍
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "WORKBENCH_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if o.strip()
]


@dataclass(frozen=True)
class Credentials:
    """一次解析结果；token 只在内存流转，repr 不打印明文。"""

    token: str
    auth_mode: str  # ctrl | open
    source: str     # env:SIM_CTRL_TOKEN / env:SIM_TOKEN / file:ctrlToken / file:openTokens / none

    @property
    def header_name(self) -> str:
        return "X-Ctrl-Token" if self.auth_mode == AUTH_CTRL else "X-Open-Token"

    def __repr__(self) -> str:  # 防止意外把令牌打进日志/异常
        return (
            f"Credentials(auth_mode={self.auth_mode!r}, source={self.source!r}, "
            f"token={'***' if self.token else ''})"
        )


def _read_gateway_file(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_credentials(
    *,
    auth_mode: str | None = None,
    token: str | None = None,
    ctrl_token: str | None = None,
    token_file: str | None = None,
) -> Credentials:
    """按 SIM_AUTH 解析令牌；参数化是为了可单测，生产走模块常量。

    关键取舍：`ctrl` 模式下**不会**悄悄退回公开令牌——那会把 workbench 的轮询
    写进 agent 统计台账。找不到 ctrlToken 时返回空 token，由调用方显式告警；
    确实要用公开令牌，必须显式 `SIM_AUTH=open`。
    """
    mode = (auth_mode or SIM_AUTH or AUTH_CTRL).strip().lower()
    if mode not in _AUTH_MODES:
        mode = AUTH_CTRL
    token = SIM_TOKEN if token is None else token
    ctrl_token = SIM_CTRL_TOKEN if ctrl_token is None else ctrl_token
    token_file = SIM_TOKEN_FILE if token_file is None else token_file

    if mode == AUTH_CTRL:
        if ctrl_token:
            return Credentials(ctrl_token, AUTH_CTRL, "env:SIM_CTRL_TOKEN")
        data = _read_gateway_file(token_file)
        ctrl = str(data.get("ctrlToken") or "")
        if ctrl:
            return Credentials(ctrl, AUTH_CTRL, "file:ctrlToken")
        if token:
            # 旧配置把 ctrlToken 放在 SIM_TOKEN；按 ctrl 发出，错了会 1002 而不是静默污染
            return Credentials(token, AUTH_CTRL, "env:SIM_TOKEN")
        return Credentials("", AUTH_CTRL, "none")

    if token:
        return Credentials(token, AUTH_OPEN, "env:SIM_TOKEN")
    data = _read_gateway_file(token_file)
    opens = data.get("openTokens") or []
    if opens:
        return Credentials(str(opens[0]), AUTH_OPEN, "file:openTokens")
    return Credentials("", AUTH_OPEN, "none")


def resolve_token() -> str:
    """兼容旧调用点：只取令牌字符串。新代码请用 resolve_credentials()。"""
    return resolve_credentials().token


def svcmeta_allowed(auth_mode: str, enabled: bool = True) -> bool:
    """svc-meta 是控制面接口，只有 ctrl 令牌能调。

    open 模式下强行调用会被 1006 拒绝，而且请求带 `X-Open-Token` 会写进
    agent 统计台账；所以这里直接按通道关闭，避免每轮快照制造噪声。
    """
    return bool(enabled) and auth_mode == AUTH_CTRL
