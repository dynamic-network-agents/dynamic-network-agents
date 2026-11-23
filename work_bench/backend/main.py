"""Work Bench 后端入口（最小可运行版）。

接口：
- GET  /api/health                 健康与配置状态（不含 Token）
- GET  /api/snapshot               统一快照（前端唯一数据源）
- GET  /api/candidates?serviceId=  该业务的候选路径（来自 service-paths.json）
- POST /api/repath                 唯一调试写白名单：转发 POST /services/{id}/path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .offline import load_bg_category, load_candidate_paths
from .simulator_client import SimulatorClient, SimulatorError
from .snapshot import Collector

_token = config.resolve_token()
_client = SimulatorClient(
    config.SIM_BASE_URL,
    _token,
    agent_id=config.AGENT_ID,
    timeout=config.TIMEOUT_S,
)
_bg_category = load_bg_category(config.BG_SERVICE_PATH)
_candidate_paths = load_candidate_paths(config.SERVICE_PATHS_PATH)
_collector = Collector(_client, _bg_category, detail_workers=config.DETAIL_WORKERS, detail_ttl=config.DETAIL_TTL_S)

app = FastAPI(title="B03 Work Bench", version="mini-run")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class Segment(BaseModel):
    type: str = Field(default="link", description="link|node")
    id: str


class RepathRequest(BaseModel):
    serviceId: str
    srcNodeId: str
    dstNodeId: str
    segments: list[Segment]


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "sim_base_url": config.SIM_BASE_URL,
        "token_configured": bool(_token),
        "bg_service_path": config.BG_SERVICE_PATH or None,
        "bg_service_count": len(_bg_category),
        "service_paths_path": config.SERVICE_PATHS_PATH or None,
        "candidate_service_count": len(_candidate_paths),
        "events_cursor": _collector.events_cursor,
    }


@app.get("/api/snapshot")
def snapshot() -> dict:
    return _collector.snapshot()


@app.get("/api/candidates")
def candidates(serviceId: str) -> dict[str, Any]:
    paths = _candidate_paths.get(serviceId)
    if paths is None:
        raise HTTPException(status_code=404, detail=f"无候选路径: {serviceId}")
    return {"serviceId": serviceId, "paths": paths}


@app.post("/api/repath")
def repath(req: RepathRequest) -> JSONResponse:
    segments = [{"type": s.type, "id": s.id} for s in req.segments]
    try:
        result = _client.set_service_path(
            req.serviceId, req.srcNodeId, req.dstNodeId, segments
        )
    except SimulatorError as exc:
        # accepted 之外的 rejected/错误，原样把 code/msg 回给前端展示
        return JSONResponse(
            status_code=200,
            content={"ok": False, "code": exc.code, "msg": exc.msg, "envelope": exc.envelope},
        )
    return JSONResponse(status_code=200, content={"ok": True, **result})


# 托管前端构建产物（单进程部署：后端同源服务前端，免 CORS、免 Node）。
# 置于所有 /api 路由之后注册，确保 API 优先匹配；dist 不存在则退回纯 API（dev 模式走 vite）。
_static_dir = config.STATIC_DIR
if _static_dir and Path(_static_dir).is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="frontend")
