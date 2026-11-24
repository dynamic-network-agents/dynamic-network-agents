"""统一 Network Snapshot 聚合（pydantic 契约版）。

一次采集 topo + links(分页取全) + services(分页取全 + 详情) + events(增量) + time，
输出可校验的 `Snapshot` 模型。所有子采集失败均被隔离，不会导致整次快照失败。

数据健康（企划书 4.4）：
- live          最近一次采集成功且数据在新鲜窗口内
- partial       部分核心资源失败，但缓存仍在新鲜窗口内
- stale         仍有数据，但已超过刷新周期（含分页不完整/对账不一致）
- disconnected  核心资源全部失败（有缓存就返回缓存，并标注 age）
- offline       仅使用离线场景文件，未连接仿真器（显式 WORKBENCH_OFFLINE=1）
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from .analysis import METRICS, build_flows, build_link_loads, check_static, compose_qos
from .models import (
    Link,
    Node,
    Pagination,
    ResourcePage,
    Service,
    Snapshot,
    SvcMetaStatus,
)
from .simulator_client import SimulatorClient, SimulatorError

MAX_EVENTS_BUFFER = 500
CORE_RESOURCES = ("topology", "links", "services")
# 详情失败率超过该比例，认为业务快照不完整（避免个别超时把状态长期打成 partial）
DETAIL_FAIL_RATIO = 0.2


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Outcome:
    nodes: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    services: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    events_cursor: int = 0
    sim_time_us: Optional[int] = None
    instance_id: Optional[str] = None
    scenario_id: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok: dict[str, bool] = field(default_factory=dict)
    svc_meta: SvcMetaStatus = field(default_factory=SvcMetaStatus)
    pagination: Pagination = field(default_factory=Pagination)


class Collector:
    """持有采集器状态（事件游标/缓存/健康基线），线程安全。"""

    def __init__(
        self,
        client: SimulatorClient,
        bg_category: dict[str, str],
        detail_workers: int = 8,
        detail_ttl: float = 4.0,
        svcmeta_enabled: bool = True,
        stale_after_s: float = 6.0,
        page_size: int = 500,
        max_pages: int = 20,
        offline: bool = False,
        offline_scene: Optional[dict] = None,
        offline_services: Optional[list[dict]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.client = client
        self.bg_category = bg_category
        self.detail_workers = detail_workers
        self.detail_ttl = detail_ttl
        self.svcmeta_enabled = svcmeta_enabled
        self.stale_after_s = stale_after_s
        self.page_size = page_size
        self.max_pages = max_pages
        self.offline = offline
        self.offline_scene = offline_scene or {}
        self.offline_services = offline_services or []
        self.clock = clock

        self._lock = threading.Lock()
        self.events_cursor = 0
        self.events_buffer: list[dict] = []
        self.last_instance_id: Optional[str] = None
        self.last_scenario_id: Optional[str] = None
        self._detail_cache: dict[str, dict] = {}
        self._prev: dict[str, list] = {}
        self._last_ok_at: dict[str, float] = {}
        self._last_success_iso: Optional[str] = None

    # ------------------------------------------------------------------ 对外
    def snapshot(self) -> Snapshot:
        with self._lock:
            if self.offline:
                return self._offline_snapshot()
            return self._live_snapshot()

    # ------------------------------------------------------------------ 实时
    def _live_snapshot(self) -> Snapshot:
        now = self.clock()
        outcome = _build(
            self.client,
            bg_category=self.bg_category,
            svcmeta_enabled=self.svcmeta_enabled,
            events_cursor=self.events_cursor,
            detail_workers=self.detail_workers,
            detail_cache=self._detail_cache,
            detail_ttl=self.detail_ttl,
            page_size=self.page_size,
            max_pages=self.max_pages,
            last_instance_id=self.last_instance_id,
            last_scenario_id=self.last_scenario_id,
        )

        for res, ok in outcome.ok.items():
            if ok:
                self._last_ok_at[res] = now

        parts = {
            "topology": outcome.nodes,
            "links": outcome.links,
            "services": outcome.services,
        }
        stale_resources: list[str] = []
        for res in CORE_RESOURCES:
            if not outcome.ok.get(res):
                if self._prev.get(res) is not None:
                    parts[res] = self._prev[res]
                    stale_resources.append(res)
                else:
                    parts[res] = []

        links_by_id = {str(l["linkId"]): l for l in parts["links"] if l.get("linkId")}
        _enrich_static_services(parts["services"], links_by_id)
        for res in CORE_RESOURCES:
            if outcome.ok.get(res):
                self._prev[res] = parts[res]

        flows = build_flows(parts["services"], parts["topology"], parts["links"])
        link_loads = build_link_loads(parts["links"], flows, parts["services"])

        ages: list[float] = []
        for res in CORE_RESOURCES:
            at = self._last_ok_at.get(res)
            ages.append(float("inf") if at is None else max(0.0, now - at))
        oldest_age = max(ages)

        core_ok = [outcome.ok.get(r, False) for r in CORE_RESOURCES]
        all_fail = not any(core_ok)
        some_fail = not all(core_ok)
        pagination_ok = (
            outcome.pagination.links.complete
            and outcome.pagination.services.complete
            and outcome.pagination.consistent is not False
        )

        if all_fail:
            health = "disconnected"
        elif some_fail or not pagination_ok:
            health = "stale" if oldest_age > self.stale_after_s else "partial"
        elif oldest_age > self.stale_after_s:
            health = "stale"
        else:
            health = "live"

        if not all_fail:
            self._last_success_iso = _iso_now()
        if oldest_age == float("inf"):
            data_age: Optional[float] = None
        else:
            data_age = round(oldest_age, 3)

        events = outcome.events or []
        self.events_buffer.extend(events)
        if len(self.events_buffer) > MAX_EVENTS_BUFFER:
            del self.events_buffer[: len(self.events_buffer) - MAX_EVENTS_BUFFER]
        self.events_cursor = outcome.events_cursor or self.events_cursor
        self.last_instance_id = outcome.instance_id or self.last_instance_id
        self.last_scenario_id = outcome.scenario_id or self.last_scenario_id

        return Snapshot(
            health=health,
            received_at=_iso_now(),
            instance_id=self.last_instance_id,
            scenario_id=self.last_scenario_id,
            sim_time_us=outcome.sim_time_us,
            errors=outcome.errors,
            warnings=outcome.warnings,
            svc_meta=outcome.svc_meta,
            pagination=outcome.pagination,
            nodes=[Node.model_validate(n) for n in parts["topology"]],
            links=[Link.model_validate(x) for x in parts["links"]],
            services=[Service.model_validate(s) for s in parts["services"]],
            flows=flows,
            linkLoads=link_loads,
            events=list(self.events_buffer),
            events_cursor=self.events_cursor,
            last_success_at=self._last_success_iso,
            data_age_s=data_age,
            stale_resources=stale_resources,
        )

    # ------------------------------------------------------------------ 离线
    def _offline_snapshot(self) -> Snapshot:
        scene = self.offline_scene
        nodes = [Node.model_validate(n) for n in scene.get("nodes") or []]
        links = [Link.model_validate(x) for x in scene.get("links") or []]
        service_dicts = [
            {
                **s,
                "category": s.get("category")
                or self.bg_category.get(str(s.get("serviceId")), "unknown"),
                "categorySource": "offline_mapping",
                "status": "unknown",
                "path": None,
                "actual": None,
                "detailError": None,
            }
            for s in self.offline_services
        ]
        flows = build_flows(service_dicts, scene.get("nodes") or [], scene.get("links") or [])
        link_loads = build_link_loads(scene.get("links") or [], flows, service_dicts)
        return Snapshot(
            health="offline",
            offline=True,
            received_at=_iso_now(),
            instance_id=None,
            scenario_id=scene.get("scenarioId") or None,
            sim_time_us=None,
            errors=[],
            warnings=["离线模式：数据来自 net-topo.json / bg-service.json，非当前运行状态"],
            svc_meta=SvcMetaStatus(enabled=False, ok=False, count=0, error="offline"),
            pagination=Pagination(
                links=ResourcePage(pages=0, count=len(links), complete=True),
                services=ResourcePage(pages=0, count=len(service_dicts), complete=True),
                note="offline",
            ),
            nodes=nodes,
            links=links,
            services=[Service.model_validate(s) for s in service_dicts],
            flows=flows,
            linkLoads=link_loads,
            events=[],
            events_cursor=0,
            last_success_at=None,
            data_age_s=None,
        )


# ---------------------------------------------------------------------- 静态 QoS
def _enrich_static_services(services: list[dict], links_by_id: dict[str, dict]) -> None:
    """给每条业务补 staticQoS / staticCheck（就地修改）。

    路径链路缺失时不做部分合成（会把时延/带宽算低），只标 missingParams。
    """
    for svc in services or []:
        segments = (svc.get("path") or {}).get("segments") or []
        ids = [
            str(seg.get("id"))
            for seg in segments
            if isinstance(seg, dict) and seg.get("type") == "link" and seg.get("id")
        ]
        missing = [lid for lid in ids if lid not in links_by_id]
        if ids and not missing:
            qos = compose_qos([links_by_id[lid] for lid in ids])
            svc["staticQoS"] = qos
            svc["staticCheck"] = check_static(qos, svc.get("requirement"))
        elif ids:
            qos = compose_qos([])
            qos["missingParams"] = [f"link:{lid}" for lid in missing]
            for metric in METRICS:
                qos[metric] = None
            svc["staticQoS"] = qos
            svc["staticCheck"] = None
        else:
            svc["staticQoS"] = None
            svc["staticCheck"] = None


# ---------------------------------------------------------------------- 采集
def _build(
    client: SimulatorClient,
    *,
    bg_category: dict[str, str],
    svcmeta_enabled: bool,
    events_cursor: int,
    detail_workers: int,
    detail_cache: dict[str, dict],
    detail_ttl: float,
    page_size: int,
    max_pages: int,
    last_instance_id: Optional[str],
    last_scenario_id: Optional[str],
) -> Outcome:
    out = Outcome(events_cursor=events_cursor)
    out.ok = {r: False for r in CORE_RESOURCES}
    out.ok["events"] = False
    out.ok["time"] = False

    # 1) 拓扑（节点含坐标/状态；links 不带 params，用数量对账分页）
    topo_links = None
    try:
        topo = client.get_topology() or {}
        out.nodes = topo.get("nodes") or []
        topo_links = len(topo.get("links") or [])
        out.ok["topology"] = True
    except SimulatorError as exc:
        out.errors.append(f"topology: {exc.code}")

    # 2) 链路（分页取全）
    links: list[dict] = []
    link_pages = 0
    link_complete = False
    try:
        links, link_pages, link_complete = client.get_links_all(page_size, max_pages)
        out.ok["links"] = True
    except SimulatorError as exc:
        out.errors.append(f"links: {exc.code}")

    # 3) 时间
    try:
        out.sim_time_us = (client.get_time() or {}).get("tsUs")
        out.ok["time"] = True
    except SimulatorError as exc:
        out.errors.append(f"time: {exc.code}")

    # 4) 业务分类（实时 svc-meta，失败退离线映射）
    live_category, svc_meta = _load_svc_meta(client, svcmeta_enabled)
    out.svc_meta = svc_meta

    # 5) 业务列表（分页取全）+ 详情
    svc_list: list[dict] = []
    svc_pages = 0
    svc_complete = False
    try:
        svc_list, svc_pages, svc_complete = client.get_services_all(page_size, max_pages)
        out.ok["services"] = True
    except SimulatorError as exc:
        out.errors.append(f"services: {exc.code}")

    if svc_list:
        now = time.monotonic()
        results: dict[str, dict] = {}
        to_fetch: list[dict] = []
        for s in svc_list:
            sid = s.get("serviceId")
            entry = detail_cache.get(sid)
            if entry is not None and (now - entry["at"]) < detail_ttl:
                results[sid] = entry["svc"]
            else:
                to_fetch.append(s)
        failed = 0
        if to_fetch:
            with ThreadPoolExecutor(max_workers=detail_workers) as pool:
                futures = {
                    pool.submit(_with_detail, client, s, bg_category, live_category): s
                    for s in to_fetch
                }
                for fut in as_completed(futures):
                    item = fut.result()
                    if item.detailError:
                        failed += 1
                    results[item.serviceId] = item
                    detail_cache[item.serviceId] = {"at": now, "svc": item}
        out.services = [
            (results[s["serviceId"]].model_dump() if results.get(s["serviceId"]) else dict(s))
            for s in svc_list
            if s.get("serviceId")
        ]
        if svc_list and failed / len(svc_list) > DETAIL_FAIL_RATIO:
            out.errors.append(f"services.detail: {failed}/{len(svc_list)} 失败")
            out.ok["services"] = False

    # 6) 事件（增量）
    try:
        ev = client.get_events(since_ts_us=events_cursor, limit=500) or {}
        out.events = ev.get("events") or []
        out.events_cursor = ev.get("nextSinceTsUs", events_cursor)
        out.ok["events"] = True
    except SimulatorError as exc:
        out.errors.append(f"events: {exc.code}")

    # 7) 分页对账
    consistent: Optional[bool] = None
    if out.ok["links"] and topo_links is not None:
        consistent = len(links) == topo_links
    note = None
    if not link_complete:
        note = f"links 分页未读完（{link_pages} 页），可能被截断"
    if consistent is False:
        note = f"links 分页累计 {len(links)} 条 ≠ /topology {topo_links} 条"
    out.pagination = Pagination(
        links=ResourcePage(pages=link_pages, count=len(links), complete=link_complete),
        services=ResourcePage(pages=svc_pages, count=len(svc_list), complete=svc_complete),
        topology_links=topo_links,
        consistent=consistent if out.ok["links"] and topo_links is not None else None,
        note=note,
    )
    out.links = links

    # 8) 实例/场景（事件不含 suiteId，从事件 payload 提取）
    out.instance_id = last_instance_id
    out.scenario_id = last_scenario_id
    for evt in out.events:
        payload = evt.get("payload") or {}
        if payload.get("instanceId"):
            out.instance_id = payload["instanceId"]
        if payload.get("scenarioId"):
            out.scenario_id = payload["scenarioId"]

    return out


def _load_svc_meta(
    client: SimulatorClient, enabled: bool
) -> tuple[dict[str, str], SvcMetaStatus]:
    """拉 svc-meta → ({serviceId: category}, 状态)。

    失败不算核心资源失败：分类是增强项，缺了退离线映射即可。
    """
    status = SvcMetaStatus(enabled=enabled, ok=False, count=0, error=None)
    if not enabled:
        status.error = "disabled"
        return {}, status
    try:
        meta = client.get_svc_meta()
    except SimulatorError as exc:
        status.error = f"{exc.code}: {exc.msg}"
        return {}, status
    live: dict[str, str] = {}
    for sid, item in meta.items():
        cat = (item or {}).get("category") if isinstance(item, dict) else None
        if sid and cat:
            live[str(sid)] = str(cat)
    status.ok = True
    status.count = len(live)
    return live, status


def _with_detail(
    client: SimulatorClient,
    svc: dict,
    bg_category: dict[str, str],
    live_category: dict[str, str],
) -> Service:
    sid = str(svc.get("serviceId", ""))
    out = dict(svc)
    if sid in live_category:
        out["category"] = live_category[sid]
        out["categorySource"] = "simulator"
    elif sid in bg_category:
        out["category"] = bg_category[sid]
        out["categorySource"] = "offline_mapping"
    else:
        out["category"] = "unknown"
        out["categorySource"] = "unknown"
    out["requirement"] = None
    out["path"] = None
    out["actual"] = None
    out["detailError"] = None
    try:
        detail = client.get_service(sid)
        out["requirement"] = detail.get("requirement")
        out["path"] = detail.get("path")
        out["actual"] = detail.get("actual")
    except SimulatorError as exc:
        out["detailError"] = f"{exc.code}: {exc.msg}"
    return Service.model_validate(out)
