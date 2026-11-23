"""work_bench 后端配置：只从环境变量 / .env 读取，Token 绝不下发前端、不进日志。"""
from __future__ import annotations

import json
import os
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent


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


_load_dotenv()

SIM_BASE_URL = os.environ.get("SIM_BASE_URL", "http://127.0.0.1:10100/api/open/v1")
SIM_TOKEN = os.environ.get("SIM_TOKEN", "")
SIM_TOKEN_FILE = os.environ.get("SIM_TOKEN_FILE", "")
AGENT_ID = os.environ.get("WORKBENCH_AGENT_ID", "workbench")
TIMEOUT_S = float(os.environ.get("SIM_TIMEOUT_S", "6"))
DETAIL_WORKERS = int(os.environ.get("SIM_DETAIL_WORKERS", "8"))
DETAIL_TTL_S = float(os.environ.get("SIM_DETAIL_TTL_S", "4"))

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


def resolve_token() -> str:
    """优先 SIM_TOKEN；否则从 SIM_TOKEN_FILE（gateway.json 风格）读 openTokens[0]。"""
    if SIM_TOKEN:
        return SIM_TOKEN
    if SIM_TOKEN_FILE and os.path.exists(SIM_TOKEN_FILE):
        try:
            data = json.loads(Path(SIM_TOKEN_FILE).read_text(encoding="utf-8"))
            tokens = data.get("openTokens") or []
            if tokens:
                return str(tokens[0])
        except (OSError, ValueError, TypeError):
            return ""
    return ""
