"""网络实体数据模型：node / link / service / path / event。

字段名对齐公开 API 的 JSON 字段（camelCase），内部用 snake_case；
每个 dataclass 提供 `from_dict` 解析，缺失字段给安全默认值。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------- 节点
@dataclass
class Position:
    x: float
    y: float

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["Position"]:
        if not d:
            return None
        return cls(x=float(d.get("x", 0.0)), y=float(d.get("y", 0.0)))


@dataclass
class Node:
    node_id: str
    name: str = ""
    node_type: str = ""            # uav / ground / air
    ip: Optional[str] = None
    mask: Optional[str] = None
    position: Optional[Position] = None
    status: str = "online"         # online / offline

    @property
    def online(self) -> bool:
        return self.status == "online"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Node":
        return cls(
            node_id=d["nodeId"],
            name=d.get("name", ""),
            node_type=d.get("nodeType", ""),
            ip=d.get("ip"),
            mask=d.get("mask"),
            position=Position.from_dict(d.get("position")),
            status=d.get("status", "online"),
        )


# --------------------------------------------------------------------------- 链路
@dataclass
class LinkParams:
    delay_ms: float
    jitter_ms: float
    bandwidth_bps: int
    ber: float
    packet_loss_rate: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LinkParams":
        return cls(
            delay_ms=float(d["delayMs"]),
            jitter_ms=float(d["jitterMs"]),
            bandwidth_bps=int(d["bandwidthBps"]),
            ber=float(d["ber"]),
            packet_loss_rate=float(d["packetLossRate"]),
        )


@dataclass
class Link:
    link_id: str
    link_type: str                 # fiber / satcom / vhf / uhf / microwave / 5g
    src_node_id: str
    dst_node_id: str
    status: str = "up"             # up / down
    params: Optional[LinkParams] = None

    @property
    def up(self) -> bool:
        return self.status == "up"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Link":
        p = d.get("params")
        return cls(
            link_id=d["linkId"],
            link_type=d.get("linkType", ""),
            src_node_id=d["srcNodeId"],
            dst_node_id=d["dstNodeId"],
            status=d.get("status", "up"),
            params=LinkParams.from_dict(p) if p else None,
        )


# --------------------------------------------------------------------------- 业务
@dataclass
class Requirement:
    """业务 QoS 需求：时延/抖动/丢包/误码为上界，带宽为下界。"""
    delay_ms: float
    jitter_ms: float
    bandwidth_bps: int
    ber: float
    packet_loss_rate: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Requirement":
        return cls(
            delay_ms=float(d["delayMs"]),
            jitter_ms=float(d["jitterMs"]),
            bandwidth_bps=int(d["bandwidthBps"]),
            ber=float(d["ber"]),
            packet_loss_rate=float(d["packetLossRate"]),
        )


@dataclass
class Segment:
    type: str                      # link / node
    id: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Segment":
        return cls(type=d.get("type", "link"), id=d.get("id", ""))


@dataclass
class ServicePath:
    path_id: str
    segments: list[Segment] = field(default_factory=list)

    @property
    def link_ids(self) -> list[str]:
        """段列表中 type=link 的链路 id 序列（去掉 type=node 段）。"""
        return [seg.id for seg in self.segments if seg.type == "link"]

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["ServicePath"]:
        if not d:
            return None
        return cls(
            path_id=d.get("pathId", ""),
            segments=[Segment.from_dict(s) for s in d.get("segments", [])],
        )


@dataclass
class Actual:
    """最近约 1 秒实测值。"""
    avg_delay_ms: float
    jitter_ms: float
    eff_bw_bps: int
    err_pct: float                 # 百分比 0~100
    packet_loss_rate: float        # 0~1
    qos_meet: Optional[bool] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["Actual"]:
        if not d:
            return None
        return cls(
            avg_delay_ms=float(d["avgDelayMs"]),
            jitter_ms=float(d["jitterMs"]),
            eff_bw_bps=int(d["effBwBps"]),
            err_pct=float(d["errPct"]),
            packet_loss_rate=float(d["packetLossRate"]),
            qos_meet=d.get("qosMeet"),
        )


@dataclass
class Service:
    service_id: str
    service_type: str = ""         # data / image / voice / video
    src_node_id: str = ""
    dst_node_id: str = ""
    priority: int = 0              # 1~8，只读
    status: str = ""               # pending/running/stopped/finished/failed
    category: str = ""             # background / test（仅 test 计分）
    requirement: Optional[Requirement] = None
    path: Optional[ServicePath] = None
    actual: Optional[Actual] = None

    @property
    def is_test(self) -> bool:
        """是否 test 业务（A2：只保 test），**仅看 `category`**。

        `category` 优先来自内部 `/api/ctrl/v1/svc-meta`（需 ctrlToken）；公开
        API 不返回该字段。需要 `TSV*` 前缀兜底时，用
        `math_modeling.flow.service_is_test(service)`（本属性不做兜底，避免
        models ↔ flow 反向依赖）。
        """
        return self.category == "test"

    @property
    def flow_key(self) -> tuple[str, str]:
        """flow 键 = 无序端点对（与仿真器 `_flow_for` 的 (ip1,ip2)/(ip2,ip1) 匹配对齐）。

        同一对 UAV 的正反两条业务落在同一个 flow 下，共用一条路径。
        """
        a, b = self.src_node_id, self.dst_node_id
        return (a, b) if a <= b else (b, a)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Service":
        req = d.get("requirement")
        return cls(
            service_id=d["serviceId"],
            service_type=d.get("serviceType", ""),
            src_node_id=d.get("srcNodeId", ""),
            dst_node_id=d.get("dstNodeId", ""),
            priority=int(d.get("priority", 0)),
            status=d.get("status", ""),
            category=d.get("category", ""),
            requirement=Requirement.from_dict(req) if req else None,
            path=ServicePath.from_dict(d.get("path")),
            actual=Actual.from_dict(d.get("actual")),
        )


# --------------------------------------------------------------------------- 事件
@dataclass
class Event:
    event_id: str
    type: str                      # node_state_changed / link_state_changed / service_state_changed
    time: str = ""
    ts_us: int = 0
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Event":
        return cls(
            event_id=d.get("eventId", ""),
            type=d.get("type", ""),
            time=d.get("time", ""),
            ts_us=int(d.get("tsUs", 0)),
            payload=d.get("payload", {}),
        )
