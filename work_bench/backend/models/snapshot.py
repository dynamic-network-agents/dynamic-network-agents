"""快照数据契约。

层级：Snapshot → Node / Link / Service；Service → Path / Requirement / Actual。

字段口径（与仿真器对齐，勿臆造）：
- 链路五项参数：delayMs / jitterMs / bandwidthBps / ber / packetLossRate；
- `actual` 只有 6 键：avgDelayMs / jitterMs / effBwBps / errPct / packetLossRate / qosMeet；
- `errPct` 是百分数（0~100），`requirement.ber` 是小数（0~1），不可直接比较；
- `path.segments` 只有 `{type:"link", id, auto?}`，没有 node 元素。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    model_config = ConfigDict(extra="allow")

    x: float
    y: float


class LinkParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    delayMs: float | None = None
    jitterMs: float | None = None
    bandwidthBps: float | None = None
    ber: float | None = None
    packetLossRate: float | None = None


class Requirement(LinkParams):
    """QoS 需求：时延/抖动/误码/丢包为上限，带宽为下限。"""


class Actual(BaseModel):
    model_config = ConfigDict(extra="allow")

    avgDelayMs: float | None = None
    jitterMs: float | None = None
    effBwBps: float | None = None
    errPct: float | None = None
    packetLossRate: float | None = None
    qosMeet: bool | None = None


class Node(BaseModel):
    model_config = ConfigDict(extra="allow")

    nodeId: str
    name: str | None = None
    nodeType: str | None = None
    ip: str | None = None
    mask: str | None = None
    position: Position | None = None
    status: str | None = None


class Link(BaseModel):
    model_config = ConfigDict(extra="allow")

    linkId: str
    linkType: str | None = None
    srcNodeId: str
    dstNodeId: str
    status: str | None = None
    params: LinkParams | None = None


class PathSegment(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    id: str
    auto: bool | None = None


class ServicePath(BaseModel):
    model_config = ConfigDict(extra="allow")

    pathId: str | None = None
    segments: list[PathSegment] = Field(default_factory=list)


class Service(BaseModel):
    model_config = ConfigDict(extra="allow")

    serviceId: str
    serviceType: str | None = None
    srcNodeId: str | None = None
    dstNodeId: str | None = None
    priority: int | None = None
    status: str | None = None
    category: str | None = None
    categorySource: str | None = None
    requirement: Requirement | None = None
    path: ServicePath | None = None
    actual: Actual | None = None
    staticQoS: QoSComposed | None = None
    staticCheck: StaticCheck | None = None
    detailError: str | None = None


class Flow(BaseModel):
    """路径控制对象：同一对源/目的（IP 对，无视方向）的业务共享一条路径。"""

    model_config = ConfigDict(extra="allow")

    flowKey: str
    srcNodeId: str | None = None
    dstNodeId: str | None = None
    srcIp: str | None = None
    dstIp: str | None = None
    memberServiceIds: list[str] = Field(default_factory=list)
    memberCount: int = 0
    pathId: str | None = None
    links: list[str] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)
    pathContinuous: bool | None = None
    direction: str | None = None  # forward / reverse / unknown
    missingLinks: list[str] = Field(default_factory=list)
    categoryCounts: dict[str, int] = Field(default_factory=dict)
    qosMeetTrue: int = 0
    qosMeetFalse: int = 0
    qosMeetUnknown: int = 0
    staticQoS: QoSComposed | None = None
    staticOkCount: int = 0
    staticFailCount: int = 0
    staticUnknownCount: int = 0


class QoSComposed(BaseModel):
    """静态路径 QoS：按链路参数合成（D=Σd, J=√Σj², B=min, L=1-∏(1-p), E≈Σε）。"""

    model_config = ConfigDict(extra="allow")

    linkCount: int = 0
    delayMs: float | None = None
    jitterMs: float | None = None
    bandwidthBps: float | None = None
    packetLossRate: float | None = None
    ber: float | None = None
    missingParams: list[str] = Field(default_factory=list)


class StaticCheckItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    metric: str
    required: float | None = None
    actual: float | None = None
    ok: bool | None = None
    note: str | None = None


class StaticCheck(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool | None = None
    violations: list[str] = Field(default_factory=list)
    items: list[StaticCheckItem] = Field(default_factory=list)


class LinkLoad(BaseModel):
    """链路需求侧负载（E-03）。measuredBps 是业务实测带宽汇总估计，不是链路吞吐。"""

    model_config = ConfigDict(extra="allow")

    linkId: str
    flowCount: int = 0
    serviceCount: int = 0
    demandBps: float = 0.0
    capacityBps: float | None = None
    demandUtilization: float | None = None
    measuredBps: float | None = None
    measuredIsEstimate: bool = True
    flowKeys: list[str] = Field(default_factory=list)


class SvcMetaStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    ok: bool = False
    count: int = 0
    error: str | None = None


class ResourcePage(BaseModel):
    """一个分页资源的读取结果。"""

    model_config = ConfigDict(extra="allow")

    pages: int = 0
    count: int = 0
    complete: bool = True


class Pagination(BaseModel):
    model_config = ConfigDict(extra="allow")

    links: ResourcePage = Field(default_factory=ResourcePage)
    services: ResourcePage = Field(default_factory=ResourcePage)
    # /topology 不分页、返回全量链路，用来对账分页结果
    topology_links: int | None = None
    consistent: bool | None = None
    note: str | None = None


class SvcMeta(BaseModel):
    """业务分类元数据（实时 svc-meta，失败退离线）。"""

    model_config = ConfigDict(extra="allow")

    status: SvcMetaStatus = Field(default_factory=SvcMetaStatus)


class Snapshot(BaseModel):
    """GET /api/snapshot 的响应契约。

    health 取值：live / partial / stale / disconnected / offline。
    """

    model_config = ConfigDict(extra="allow")

    snapshot_version: int = 1
    health: str
    received_at: str
    instance_id: str | None = None
    scenario_id: str | None = None
    sim_time_us: int | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    svc_meta: SvcMetaStatus = Field(default_factory=SvcMetaStatus)
    pagination: Pagination = Field(default_factory=Pagination)
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    services: list[Service] = Field(default_factory=list)
    flows: list[Flow] = Field(default_factory=list)
    linkLoads: list[LinkLoad] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    events_cursor: int = 0
    last_success_at: str | None = None
    data_age_s: float | None = None
    stale_resources: list[str] = Field(default_factory=list)
    offline: bool = False
