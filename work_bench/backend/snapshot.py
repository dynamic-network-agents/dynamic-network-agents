"""统一 Network Snapshot 聚合。

一次采集 nodes(topology，含坐标/状态) + links(含 5 项参数) + services(列表+详情，
并发受控) + events(增量) + time，并输出数据健康状态。所有子采集失败均被隔离，
不会导致整次快照失败。
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Optional

from .simulator_client import SimulatorClient, SimulatorError

MAX_EVENTS_BUFFER = 500


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Collector:
    """持有采集器状态（事件游标/缓冲、实例标识），线程安全。"""

    def __init__(self, client: SimulatorClient, bg_category: dict[str, str], detail_workers: int = 8, detail_ttl: float = 4.0):
        self.client = client
        self.bg_category = bg_category
        self.detail_workers = detail_workers
        self.detail_ttl = detail_ttl
        self._lock = threading.Lock()
        self.events_cursor = 0
        self.events_buffer: list[dict] = []
        self.last_instance_id: Optional[str] = None
        self.last_scenario_id: Optional[str] = None
        self._detail_cache: dict[str, dict] = {}

    def snapshot(self) -> dict:
        with self._lock:
            snap = _build(
                self.client,
                bg_category=self.bg_category,
                events_cursor=self.events_cursor,
                events_buffer=self.events_buffer,
                last_instance_id=self.last_instance_id,
                last_scenario_id=self.last_scenario_id,
                detail_workers=self.detail_workers,
                detail_cache=self._detail_cache,
                detail_ttl=self.detail_ttl,
            )
            self.events_cursor = snap["events_cursor"]
            self.last_instance_id = snap["instance_id"]
            self.last_scenario_id = snap["scenario_id"]
            return snap


def _build(
    client: SimulatorClient,
    *,
    bg_category: dict[str, str],
    events_cursor: int,
    events_buffer: list[dict],
    last_instance_id: Optional[str],
    last_scenario_id: Optional[str],
    detail_workers: int,
    detail_cache: dict[str, dict],
    detail_ttl: float,
) -> dict:
    received_at = _iso_now()
    errors: list[str] = []
    topo_ok = links_ok = svc_ok = False

    # 1) 拓扑（节点含坐标/状态）
    nodes: list[dict] = []
    try:
        nodes = client.get_topology().get("nodes", [])
        topo_ok = True
    except SimulatorError as exc:
        errors.append(f"topology: {exc.code}")

    # 2) 链路（含 5 项参数）
    links: list[dict] = []
    try:
        links = client.get_links().get("links", [])
        links_ok = True
    except SimulatorError as exc:
        errors.append(f"links: {exc.code}")

    # 3) 时间
    sim_time_us: Optional[int] = None
    try:
        sim_time_us = client.get_time().get("tsUs")
    except SimulatorError as exc:
        errors.append(f"time: {exc.code}")

    # 4) 业务列表 + 详情（并发受控）
    services: list[dict] = []
    svc_list: list[dict] = []
    try:
        svc_list = client.get_services().get("services", [])
        svc_ok = True
    except SimulatorError as exc:
        errors.append(f"services: {exc.code}")

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
        if to_fetch:
            with ThreadPoolExecutor(max_workers=detail_workers) as pool:
                futures = {pool.submit(_with_detail, client, s, bg_category): s for s in to_fetch}
                for fut in as_completed(futures):
                    item = fut.result()
                    results[item["serviceId"]] = item
                    detail_cache[item["serviceId"]] = {"at": now, "svc": item}
        services = [results[s["serviceId"]] for s in svc_list if s.get("serviceId") in results]

    # 5) 事件（增量）
    new_events: list[dict] = []
    next_cursor = events_cursor
    try:
        ev = client.get_events(since_ts_us=events_cursor, limit=500)
        new_events = ev.get("events", [])
        next_cursor = ev.get("nextSinceTsUs", events_cursor)
    except SimulatorError as exc:
        errors.append(f"events: {exc.code}")

    for evt in new_events:
        events_buffer.append(evt)
    if len(events_buffer) > MAX_EVENTS_BUFFER:
        del events_buffer[: len(events_buffer) - MAX_EVENTS_BUFFER]

    # 从最新事件提取 instance/scenario（事件自身不带 suiteId）
    instance_id = last_instance_id
    scenario_id = last_scenario_id
    for evt in new_events:
        payload = evt.get("payload") or {}
        if payload.get("instanceId"):
            instance_id = payload["instanceId"]
        if payload.get("scenarioId"):
            scenario_id = payload["scenarioId"]

    # 健康状态
    if not (topo_ok or links_ok or svc_ok):
        health = "disconnected"
    elif errors:
        health = "partial"
    else:
        health = "live"

    return {
        "health": health,
        "received_at": received_at,
        "instance_id": instance_id,
        "scenario_id": scenario_id,
        "sim_time_us": sim_time_us,
        "errors": errors,
        "nodes": nodes,
        "links": links,
        "services": services,
        "events": list(events_buffer),
        "events_cursor": next_cursor,
    }


def _with_detail(client: SimulatorClient, svc: dict, bg_category: dict[str, str]) -> dict:
    sid = str(svc.get("serviceId", ""))
    out = dict(svc)
    out["category"] = bg_category.get(sid, "unknown")
    out["categorySource"] = "offline_mapping" if sid in bg_category else "unknown"
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
    return out
