"""Work Bench 后端入口（最小可运行版）。

接口：
- GET  /api/health                 健康与配置状态（不含 Token）
- GET  /api/snapshot               统一快照（前端唯一数据源）
- GET  /api/candidates?serviceId=  该业务的候选路径（来自 service-paths.json）
- GET  /api/flow-candidates?flowKey= Flow 的候选路径 + 静态可行性（当前链路参数重算）
- POST /api/repath                 唯一调试写白名单：转发 POST /services/{id}/path

观测通道（v1.2 起）：默认用 `X-Ctrl-Token`（仿真器前端同款）调 `/api/open/v1`，
请求落 front_stat，不计入 `agent-calls` 的 agent 统计台账。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, policy
from .analysis import build_flow_candidates
from .models import Snapshot
from .offline import load_bg_category, load_bg_services, load_candidate_paths, load_scene
from .simulator_client import SimulatorClient, SimulatorError
from .snapshot import Collector

_creds = config.resolve_credentials()
_client = SimulatorClient(
    config.SIM_BASE_URL,
    _creds.token,
    auth_mode=_creds.auth_mode,
    ctrl_base_url=config.SIM_CTRL_BASE_URL,
    agent_id=config.AGENT_ID,
    timeout=config.TIMEOUT_S,
)
_svcmeta_enabled = config.svcmeta_allowed(_creds.auth_mode, config.SVCMETA_ENABLED)
_runinfo_enabled = config.runinfo_allowed(_creds.auth_mode, config.RUNINFO_ENABLED)
_bg_category = load_bg_category(config.BG_SERVICE_PATH)
_candidate_paths = load_candidate_paths(config.SERVICE_PATHS_PATH)
_offline_scene = load_scene(config.NET_TOPO_PATH) if config.OFFLINE_MODE else None
_offline_services = load_bg_services(config.BG_SERVICE_PATH) if config.OFFLINE_MODE else []
_collector = Collector(
    _client,
    _bg_category,
    detail_workers=config.DETAIL_WORKERS,
    detail_ttl=config.DETAIL_TTL_S,
    svcmeta_enabled=_svcmeta_enabled,
    runinfo_enabled=_runinfo_enabled,
    stale_after_s=config.STALE_AFTER_S,
    page_size=config.PAGE_SIZE,
    max_pages=config.MAX_PAGES,
    offline=config.OFFLINE_MODE,
    offline_scene=_offline_scene,
    offline_services=_offline_services,
)


def _startup_notice() -> None:
    """启动时的口径提示：只说明通道，不打印令牌。"""
    if not _creds.token:
        print(
            "[workbench] 未找到令牌：ctrl 模式不会退回公开令牌（会污染 agent 调用统计）。"
            "请设置 SIM_CTRL_TOKEN / SIM_TOKEN_FILE，或显式 SIM_AUTH=open 降级。",
            file=sys.stderr,
        )
    elif _creds.auth_mode != config.AUTH_CTRL:
        print(
            "[workbench] SIM_AUTH=open：观测走公开令牌，调用会计入 agent 统计台账；"
            "正式跑请改回 ctrl。",
            file=sys.stderr,
        )
    elif _creds.source == "env:SIM_TOKEN":
        print(
            "[workbench] 注意：ctrl 模式下 SIM_TOKEN 被当作 ctrl 令牌发送；"
            "若它其实是公开令牌，请置 SIM_AUTH=open（会污染统计）。",
            file=sys.stderr,
        )
    if config.SVCMETA_ENABLED and not _svcmeta_enabled:
        print(
            "[workbench] svc-meta 已禁用：open 令牌只能调公开 API，无法取实时分类。",
            file=sys.stderr,
        )
    if config.RUNINFO_ENABLED and not _runinfo_enabled:
        print(
            "[workbench] run-info 已禁用：open 令牌取不到运行态，"
            "顶栏状态/仿真时间将显示「未知」。",
            file=sys.stderr,
        )
    if config.OFFLINE_MODE:
        print(
            "[workbench] WORKBENCH_OFFLINE=1：仅读离线场景，不连接仿真器"
            f"（NET_TOPO_PATH={'已配置' if config.NET_TOPO_PATH else '未配置'}）。",
            file=sys.stderr,
        )
    if not config.ALLOW_REPATH:
        print("[workbench] WORKBENCH_ALLOW_REPATH=0：/api/repath 已禁用。", file=sys.stderr)


_startup_notice()

app = FastAPI(title="B03 Work Bench", version="v1.2")

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
        "sim_ctrl_base_url": config.SIM_CTRL_BASE_URL or None,
        "auth_mode": _creds.auth_mode,
        "token_configured": bool(_creds.token),
        "token_source": _creds.source,
        "svcmeta_enabled": _svcmeta_enabled,
        "runinfo_enabled": _runinfo_enabled,
        "repath_enabled": config.ALLOW_REPATH,
        "offline": config.OFFLINE_MODE,
        "net_topo_path": config.NET_TOPO_PATH or None,
        "stale_after_s": config.STALE_AFTER_S,
        "bg_service_path": config.BG_SERVICE_PATH or None,
        "bg_service_count": len(_bg_category),
        "service_paths_path": config.SERVICE_PATHS_PATH or None,
        "candidate_service_count": len(_candidate_paths),
        "events_cursor": _collector.events_cursor,
    }


@app.get("/api/snapshot", response_model=Snapshot)
def snapshot() -> Snapshot:
    return _collector.snapshot()


@app.get("/api/candidates")
def candidates(serviceId: str) -> dict[str, Any]:
    paths = _candidate_paths.get(serviceId)
    if paths is None:
        raise HTTPException(status_code=404, detail=f"无候选路径: {serviceId}")
    return {"serviceId": serviceId, "paths": paths}


@app.get("/api/flow-candidates")
def flow_candidates(flowKey: str) -> dict[str, Any]:
    """Flow 候选路径与静态可行性：用最近一次快照的链路参数重算，不触发新采集。

    候选路径只来自离线 `service-paths.json`（公开 API 不提供候选生成），
    文件里的 metrics 是计划期值，因此这里不用它，改为按当前 /links 合成。
    """
    snap = _collector.latest()
    if snap is None:
        raise HTTPException(status_code=503, detail="尚无快照，请等待一次采集完成")
    flow = next((f for f in snap.flows if f.flowKey == flowKey), None)
    if flow is None:
        raise HTTPException(status_code=404, detail=f"当前快照没有该 Flow: {flowKey}")
    return build_flow_candidates(
        flow.model_dump(),
        [s.model_dump() for s in snap.services],
        [link.model_dump() for link in snap.links],
        _candidate_paths,
    )


@app.post("/api/repath")
def repath(req: RepathRequest) -> JSONResponse:
    try:
        policy.ensure_repath_allowed(config.ALLOW_REPATH)
    except policy.RepathDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None

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
    return JSONResponse(
        status_code=200,
        content={"ok": True, **result, "warning": policy.EVENT_RECORD_WARNING},
    )


# 托管前端构建产物（单进程部署：后端同源服务前端，免 CORS、免 Node）。
# 置于所有 /api 路由之后注册，确保 API 优先匹配；dist 不存在则退回纯 API（dev 模式走 vite）。
_static_dir = config.STATIC_DIR
if _static_dir and Path(_static_dir).is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="frontend")
