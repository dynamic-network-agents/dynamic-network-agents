import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCandidates, fetchSnapshot, postRepath, type RepathResult } from "./api";
import type { CandidatePath, Flow, Service, Snapshot } from "./types";
import ServiceDetail from "./ServiceDetail";
import TopologyView from "./TopologyView";

const POLL_MS = 2000;

function fmtUs(us: number | null | undefined): string {
  if (us == null) return "—";
  return new Date(Math.floor(us / 1000)).toLocaleString();
}

function mbps(bps?: number | null): string {
  return bps === null || bps === undefined ? "—" : (bps / 1e6).toFixed(1);
}

function utilPct(u?: number | null): string {
  return u === null || u === undefined ? "—" : `${(u * 100).toFixed(0)}%`;
}

function segSummary(segments?: { type: string; id: string }[] | null): string {
  if (!segments || segments.length === 0) return "—";
  return segments.map((s) => s.id).join(" → ");
}

function HealthBadge({ health }: { health: string }) {
  const cls =
    health === "live" ? "ok" : health === "partial" || health === "stale" ? "warn" : "bad";
  return <span className={`health health-${cls}`}>{health}</span>;
}

// 分类来源中文标签：simulator=实时 svc-meta，offline_mapping=离线 bg-service.json
const SOURCE_LABEL: Record<string, string> = {
  simulator: "实时",
  offline_mapping: "离线",
  unknown: "未知",
};

function categorySourceLabel(src?: string): string {
  if (!src) return SOURCE_LABEL.unknown;
  return SOURCE_LABEL[src] ?? src;
}

export default function App() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let alive = true;
    let inFlight = false;
    async function tick() {
      if (inFlight) return; // 上一轮快照未返回，跳过本轮，避免请求叠加打挂仿真器
      inFlight = true;
      try {
        const s = await fetchSnapshot();
        if (!alive) return;
        setSnap(s);
        setLastUpdate(new Date());
        setError(null);
      } catch (e) {
        if (!alive) return;
        setError(String(e));
      } finally {
        inFlight = false;
      }
    }
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const [selectedFlowKey, setSelectedFlowKey] = useState<string | null>(null);
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);

  const flows: Flow[] = useMemo(() => snap?.flows ?? [], [snap]);
  const linkLoads = useMemo(() => snap?.linkLoads ?? [], [snap]);
  const linksById = useMemo(
    () => new Map((snap?.links ?? []).map((l) => [l.linkId, l])),
    [snap]
  );
  const servicesById = useMemo(
    () => new Map((snap?.services ?? []).map((s) => [s.serviceId, s])),
    [snap]
  );

  const selectedFlow = useMemo(
    () => flows.find((f) => f.flowKey === selectedFlowKey) ?? null,
    [flows, selectedFlowKey]
  );

  const selectedService = selectedServiceId ? servicesById.get(selectedServiceId) ?? null : null;
  const selectedServiceFlow = useMemo(
    () =>
      selectedService
        ? flows.find((f) => f.memberServiceIds.includes(selectedService.serviceId)) ?? null
        : null,
    [flows, selectedService]
  );

  const highlightedLinks = useMemo(() => {
    const s = new Set<string>();
    if (selectedLinkId) {
      s.add(selectedLinkId);
      return s;
    }
    if (selectedService) {
      for (const seg of selectedService.path?.segments ?? []) {
        if (seg.type === "link") s.add(seg.id);
      }
      if (s.size > 0) return s;
    }
    if (selectedFlow) {
      for (const lid of selectedFlow.links) s.add(lid);
      return s;
    }
    for (const svc of snap?.services ?? []) {
      for (const seg of svc.path?.segments ?? []) {
        if (seg.type === "link") s.add(seg.id);
      }
    }
    return s;
  }, [snap, selectedFlow, selectedService, selectedLinkId]);

  const stats = useMemo(() => {
    const services = snap?.services ?? [];
    const meetTrue = services.filter((s) => s.actual?.qosMeet === true).length;
    const meetFalse = services.filter((s) => s.actual?.qosMeet === false).length;
    const testAll = services.filter((s) => s.category === "test");
    const testKnown = testAll.filter(
      (s) => s.actual?.qosMeet === true || s.actual?.qosMeet === false
    );
    const testTrue = testAll.filter((s) => s.actual?.qosMeet === true).length;
    return {
      total: services.length,
      running: services.filter((s) => s.status === "running").length,
      meetTrue,
      meetFalse,
      unknown: services.length - meetTrue - meetFalse,
      testTotal: testAll.length,
      testKnown: testKnown.length,
      testTrue,
      testRate: testKnown.length > 0 ? (testTrue / testKnown.length) * 100 : null,
    };
  }, [snap]);

  const countBy = useCallback(
    (cat?: string) =>
      (snap?.services ?? []).filter((s) => (cat ? s.category === cat : true)).length,
    [snap]
  );

  const sortedNodes = useMemo(
    () => [...(snap?.nodes ?? [])].sort((a, b) => (a.nodeId < b.nodeId ? -1 : a.nodeId > b.nodeId ? 1 : 0)),
    [snap]
  );
  const sortedLinks = useMemo(
    () => [...(snap?.links ?? [])].sort((a, b) => (a.linkId < b.linkId ? -1 : a.linkId > b.linkId ? 1 : 0)),
    [snap]
  );
  const sortedServices = useMemo(
    () => [...(snap?.services ?? [])].sort((a, b) => (a.serviceId < b.serviceId ? -1 : a.serviceId > b.serviceId ? 1 : 0)),
    [snap]
  );

  const visibleServices = useMemo(() => {
    if (!selectedFlow) return sortedServices;
    const ids = new Set(selectedFlow.memberServiceIds);
    return sortedServices.filter((s) => ids.has(s.serviceId));
  }, [sortedServices, selectedFlow]);

  return (
    <div className="app">
      <header className="header">
        <h1>B03 Work Bench</h1>
        <div className="header-meta">
          {snap ? <HealthBadge health={snap.health} /> : <HealthBadge health="disconnected" />}
          <span>实例 {snap?.instance_id ?? "—"}</span>
          <span>场景 {snap?.scenario_id ?? "—"}</span>
          <span>仿真时间 {fmtUs(snap?.sim_time_us)}</span>
          {snap?.data_age_s != null && <span>数据龄 {snap.data_age_s.toFixed(1)}s</span>}
          {snap?.offline && <span className="bad">离线</span>}
          {snap?.svc_meta && (
            <span>
              分类 {snap.svc_meta.ok ? "实时" : snap.svc_meta.enabled ? "离线" : "关闭"}
            </span>
          )}
          <span>最近更新 {lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}</span>
          {error && <span className="error">⚠ {error}</span>}
        </div>
        {snap && snap.errors.length > 0 && (
          <div className="errors">部分失败: {snap.errors.join(" / ")}</div>
        )}
        {snap?.pagination?.note && (
          <div className="errors">分页: {snap.pagination.note}</div>
        )}
      </header>

      <section className="stats" aria-label="总览指标">
        <div className="stat">
          <span className="muted">业务 / 运行</span>
          <b>{stats.total}</b>
          <small>运行 {stats.running}</small>
        </div>
        <div className="stat">
          <span className="muted">Flow</span>
          <b>{flows.length}</b>
          <small>路径控制对象</small>
        </div>
        <div className="stat">
          <span className="muted">test 实测达标率</span>
          <b>{stats.testRate === null ? "—" : `${stats.testRate.toFixed(0)}%`}</b>
          <small>
            {stats.testRate === null ? "无实测" : `${stats.testTrue}/${stats.testKnown}`}
          </small>
        </div>
        <div className="stat">
          <span className="muted">未达标 / 未知</span>
          <b className={stats.meetFalse > 0 ? "bad" : ""}>{stats.meetFalse}</b>
          <small>未知 {stats.unknown}</small>
        </div>
      </section>

      <section className="panel">
        <h2>拓扑</h2>
        {snap && snap.nodes.length > 0 ? (
          <TopologyView nodes={snap.nodes} links={snap.links} highlightLinks={highlightedLinks} />
        ) : (
          <p className="empty">无节点数据</p>
        )}
      </section>

      <section className="panel">
        <h2>Flow（{flows.length}）· 路径控制对象</h2>
        <p className="muted">
          同一对源/目的（IP 对，无视方向）的业务共享一条 flow 级路径；改一条 = 同时改双向，影响该 Flow 全部成员。
          点击行可只看该 Flow 的成员高亮。
        </p>
        <table>
          <thead>
            <tr>
              <th>flowKey（推导）</th><th>源 → 目的</th><th>成员业务</th><th>分类</th>
              <th>当前路径</th><th>实测达标</th><th>静态可行性</th>
            </tr>
          </thead>
          <tbody>
            {flows.map((f) => (
              <tr
                key={f.flowKey}
                className={selectedFlowKey === f.flowKey ? "running" : ""}
                onClick={() => {
                  setSelectedFlowKey(selectedFlowKey === f.flowKey ? null : f.flowKey);
                  setSelectedServiceId(null);
                  setSelectedLinkId(null);
                }}
                style={{ cursor: "pointer" }}
              >
                <td>
                  <button
                    className="linkbtn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFlowKey(f.flowKey);
                      setSelectedServiceId(null);
                      setSelectedLinkId(null);
                    }}
                  >
                    {f.flowKey}
                  </button>
                </td>
                <td>
                  {f.srcNodeId ?? "—"} → {f.dstNodeId ?? "—"}
                  {f.direction === "reverse" && <small className="muted">（路径反序下发）</small>}
                </td>
                <td>
                  {f.memberCount}
                  <small className="muted">
                    （{f.memberServiceIds.slice(0, 3).join(", ")}
                    {f.memberServiceIds.length > 3 ? "…" : ""}）
                  </small>
                </td>
                <td>
                  {Object.entries(f.categoryCounts ?? {})
                    .map(([k, v]) => `${k}×${v}`)
                    .join(" ")}
                </td>
                <td className="nowrap">
                  {f.links.join(" → ") || "—"}
                  {f.pathContinuous === false && <span className="bad"> 不连续</span>}
                  {(f.missingLinks?.length ?? 0) > 0 && (
                    <span className="bad"> 缺 {f.missingLinks!.join(",")}</span>
                  )}
                </td>
                <td className="nowrap">
                  {f.qosMeetTrue}✓ {f.qosMeetFalse}✗ {f.qosMeetUnknown}?
                </td>
                <td className="nowrap">
                  {f.staticOkCount}✓ {f.staticFailCount}✗ {f.staticUnknownCount}?
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {flows.length === 0 && <p className="empty">当前无 Flow（业务尚未启动或无可用 IP）</p>}
        {selectedFlow && (
          <p className="muted">
            已选中 {selectedFlow.flowKey}：业务表只显示其 {selectedFlow.memberCount} 条成员，拓扑只高亮该路径；再点一次该行取消。
          </p>
        )}
      </section>

      <section className="panel">
        <h2>链路负载（需求侧，{linkLoads.length}）</h2>
        <p className="muted">
          按 demand/capacity 降序；flow 数 ≠ 负载。实测列是业务 <code>effBwBps</code> 汇总估计，不是链路吞吐。
        </p>
        {linkLoads.length === 0 ? (
          <p className="empty">无路径数据（业务未运行或路径未知）</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>linkId</th><th>容量 Mbps</th><th>Flow 数</th><th>业务数</th>
                  <th>需求 Mbps</th><th>需求/容量</th><th>实测估计 Mbps</th>
                </tr>
              </thead>
              <tbody>
                {linkLoads.slice(0, 12).map((l) => (
                  <tr key={l.linkId}>
                    <td>{l.linkId}</td>
                    <td>{mbps(l.capacityBps)}</td>
                    <td>{l.flowCount}</td>
                    <td>{l.serviceCount}</td>
                    <td>{mbps(l.demandBps)}</td>
                    <td className={(l.demandUtilization ?? 0) > 1 ? "bad" : ""}>
                      {utilPct(l.demandUtilization)}
                    </td>
                    <td>{mbps(l.measuredBps)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {linkLoads.length > 12 && (
              <p className="muted">显示前 12 / 共 {linkLoads.length}（完整数据见 /api/snapshot 的 linkLoads）</p>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <h2>节点（{snap?.nodes.length ?? 0}）</h2>
        <table>
          <thead>
            <tr>
              <th>nodeId</th><th>名称</th><th>类型</th><th>状态</th><th>IP</th><th>位置</th>
            </tr>
          </thead>
          <tbody>
            {sortedNodes.map((n) => (
              <tr key={n.nodeId}>
                <td>{n.nodeId}</td>
                <td>{n.name}</td>
                <td>{n.nodeType}</td>
                <td className={n.status === "offline" ? "bad" : ""}>{n.status ?? "—"}</td>
                <td>{n.ip ?? "—"}</td>
                <td>{n.position ? `${n.position.x.toFixed(0)}, ${n.position.y.toFixed(0)}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>链路（{snap?.links.length ?? 0}）</h2>
        <table>
          <thead>
            <tr>
              <th>linkId</th><th>类型</th><th>src</th><th>dst</th><th>状态</th>
              <th>delayMs</th><th>jitterMs</th><th>带宽bps</th><th>ber</th><th>丢包率</th>
            </tr>
          </thead>
          <tbody>
            {sortedLinks.map((l) => (
              <tr key={l.linkId}>
                <td>{l.linkId}</td>
                <td>{l.linkType}</td>
                <td>{l.srcNodeId}</td>
                <td>{l.dstNodeId}</td>
                <td className={l.status === "down" ? "bad" : ""}>{l.status ?? "—"}</td>
                <td>{l.params?.delayMs ?? "—"}</td>
                <td>{l.params?.jitterMs ?? "—"}</td>
                <td>{l.params?.bandwidthBps ?? "—"}</td>
                <td>{l.params?.ber ?? "—"}</td>
                <td>{l.params?.packetLossRate ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>
          业务（{countBy()}）· 背景 {countBy("background")} · 测试 {countBy("test")} · 未知 {countBy("unknown")}
          {selectedFlow ? ` · 当前 Flow 成员 ${visibleServices.length}` : ""}
        </h2>
        <table>
          <thead>
            <tr>
              <th>serviceId</th><th>类型</th><th>分类</th><th>src</th><th>dst</th>
              <th>优先级</th><th>状态</th><th>需求</th><th>路径</th><th>实测</th>
            </tr>
          </thead>
          <tbody>
            {visibleServices.map((s) => (
              <tr
                key={s.serviceId}
                className={[
                  s.status === "running" ? "running" : "",
                  selectedServiceId === s.serviceId ? "selected" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => {
                  setSelectedServiceId(s.serviceId);
                  setSelectedLinkId(null);
                }}
                style={{ cursor: "pointer" }}
              >
                <td>
                  <button
                    className="linkbtn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedServiceId(s.serviceId);
                      setSelectedLinkId(null);
                    }}
                  >
                    {s.serviceId}
                  </button>
                </td>
                <td>{s.serviceType ?? "—"}</td>
                <td>
                  {s.category}
                  <small className="muted">（{categorySourceLabel(s.categorySource)}）</small>
                </td>
                <td>{s.srcNodeId ?? "—"}</td>
                <td>{s.dstNodeId ?? "—"}</td>
                <td>{s.priority ?? "—"}</td>
                <td>{s.status ?? "—"}</td>
                <td className="nowrap">
                  {s.requirement
                    ? `D${s.requirement.delayMs ?? "—"} J${s.requirement.jitterMs ?? "—"} B${s.requirement.bandwidthBps ?? "—"}`
                    : s.detailError ? `⚠${s.detailError}` : "—"}
                </td>
                <td className="nowrap">{segSummary(s.path?.segments)}</td>
                <td
                  className="nowrap"
                  title="D=avgDelayMs(ms) J=jitterMs(ms) B=effBwBps(bps) E=errPct(%) L=packetLossRate(0~1)；E 与需求 ber(0~1) 单位不同"
                >
                  {s.actual
                    ? `D${s.actual.avgDelayMs ?? "—"} J${s.actual.jitterMs ?? "—"} B${s.actual.effBwBps ?? "—"} E${s.actual.errPct ?? "—"}% L${s.actual.packetLossRate ?? "—"} ${
                        s.actual.qosMeet === true ? "✓" : s.actual.qosMeet === false ? "✗" : "?"
                      }`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {snap && snap.services.length === 0 && <p className="empty">当前无业务（仿真尚未启动业务）</p>}
        <p className="muted">点击业务行查看详情（需求 vs 实测、所属 Flow、路径链路）；点击链路行单独高亮。</p>
      </section>

      {selectedService && (
        <ServiceDetail
          service={selectedService}
          flow={selectedServiceFlow}
          linksById={linksById}
          onSelectFlow={(key) => {
            setSelectedFlowKey(key);
            setSelectedServiceId(null);
            setSelectedLinkId(null);
          }}
          onSelectLink={(id) => setSelectedLinkId(id)}
          onClear={() => {
            setSelectedServiceId(null);
            setSelectedLinkId(null);
          }}
        />
      )}

      <RepathPanel services={sortedServices} />

      <section className="panel">
        <h2>事件（{snap?.events.length ?? 0}，游标 {snap?.events_cursor ?? 0}）</h2>
        <table>
          <thead>
            <tr><th>eventId</th><th>类型</th><th>时间</th><th>摘要</th></tr>
          </thead>
          <tbody>
            {(snap?.events ?? []).slice().reverse().map((e) => (
              <tr key={e.eventId}>
                <td>{e.eventId}</td>
                <td>{e.type}</td>
                <td>{e.time ?? "—"}</td>
                <td className="nowrap">{JSON.stringify(e.payload)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function RepathPanel({ services }: { services: Service[] }) {
  const [serviceId, setServiceId] = useState("");
  const [candidates, setCandidates] = useState<CandidatePath[]>([]);
  const [pathIdx, setPathIdx] = useState<number>(-1);
  const [manual, setManual] = useState("");
  const [result, setResult] = useState<RepathResult | null>(null);
  const [busy, setBusy] = useState(false);

  const svc = services.find((s) => s.serviceId === serviceId);

  useEffect(() => {
    setCandidates([]);
    setPathIdx(-1);
    setResult(null);
    if (!serviceId) return;
    fetchCandidates(serviceId)
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, [serviceId]);

  const submit = async () => {
    if (!svc?.srcNodeId || !svc?.dstNodeId) return;
    let segments: { type: string; id: string }[] = [];
    if (pathIdx >= 0 && candidates[pathIdx]) {
      segments = candidates[pathIdx].links.map((id) => ({ type: "link", id }));
    } else if (manual.trim()) {
      segments = manual
        .split(/[,，\s]+/)
        .filter(Boolean)
        .map((id) => ({ type: "link", id }));
    }
    if (segments.length === 0) {
      setResult({ ok: false, msg: "未选择/填写路径" });
      return;
    }
    const ok = window.confirm(
      `确认把业务 ${serviceId} 改到路径 [${segments.map((s) => s.id).join(" → ")}]？\n\n注意：路径是 flow 级，改这一条会同时改变同源目的(${svc.srcNodeId}→${svc.dstNodeId})的其他业务。`
    );
    if (!ok) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await postRepath({
        serviceId,
        srcNodeId: svc.srcNodeId,
        dstNodeId: svc.dstNodeId,
        segments,
      });
      setResult(r);
    } catch (e) {
      setResult({ ok: false, msg: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>更改 Service（唯一写操作 · 调试用）</h2>
      <div className="repath-row">
        <select value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
          <option value="">选择业务…</option>
          {services.map((s) => (
            <option key={s.serviceId} value={s.serviceId}>
              {s.serviceId}（{s.category}）{s.srcNodeId}→{s.dstNodeId}
            </option>
          ))}
        </select>
        {svc && (
          <select value={pathIdx} onChange={(e) => setPathIdx(Number(e.target.value))}>
            <option value={-1}>候选路径（自动）…</option>
            {candidates.map((c, i) => (
              <option key={i} value={i}>
                路径{c.pathNo}：[{c.links.join(" → ")}]
              </option>
            ))}
          </select>
        )}
        <input
          placeholder="或手动填 linkId（逗号分隔）"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
        />
        <button onClick={submit} disabled={busy || !serviceId}>
          {busy ? "提交中…" : "提交更改"}
        </button>
      </div>
      <p className="muted">
        提醒：改一条业务 = 改整条 flow，会影响同源目的的其他业务；这是唯一写接口，请谨慎。
      </p>
      {result && (
        <pre className="result">
          {result.ok ? "✓ accepted" : "✗ " + (result.code ?? "") + " " + (result.msg ?? "")}
          {"\n"}
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      {result?.warning && <p className="muted">⚠ {result.warning}</p>}
    </section>
  );
}
