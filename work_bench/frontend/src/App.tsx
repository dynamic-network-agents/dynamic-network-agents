import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCandidates, fetchSnapshot, postRepath, type RepathResult } from "./api";
import type { CandidatePath, Service, Snapshot } from "./types";
import TopologyView from "./TopologyView";

const POLL_MS = 2000;

function fmtUs(us: number | null | undefined): string {
  if (us == null) return "—";
  return new Date(Math.floor(us / 1000)).toLocaleString();
}

function segSummary(segments?: { type: string; id: string }[] | null): string {
  if (!segments || segments.length === 0) return "—";
  return segments.map((s) => s.id).join(" → ");
}

function HealthBadge({ health }: { health: string }) {
  const cls = health === "live" ? "ok" : health === "partial" ? "warn" : "bad";
  return <span className={`health health-${cls}`}>{health}</span>;
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

  const highlightedLinks = useMemo(() => {
    const s = new Set<string>();
    for (const svc of snap?.services ?? []) {
      for (const seg of svc.path?.segments ?? []) {
        if (seg.type === "link") s.add(seg.id);
      }
    }
    return s;
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

  return (
    <div className="app">
      <header className="header">
        <h1>B03 Work Bench</h1>
        <div className="header-meta">
          {snap ? <HealthBadge health={snap.health} /> : <HealthBadge health="disconnected" />}
          <span>实例 {snap?.instance_id ?? "—"}</span>
          <span>场景 {snap?.scenario_id ?? "—"}</span>
          <span>仿真时间 {fmtUs(snap?.sim_time_us)}</span>
          <span>最近更新 {lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}</span>
          {error && <span className="error">⚠ {error}</span>}
        </div>
        {snap && snap.errors.length > 0 && (
          <div className="errors">部分失败: {snap.errors.join(" / ")}</div>
        )}
      </header>

      <section className="panel">
        <h2>拓扑</h2>
        {snap && snap.nodes.length > 0 ? (
          <TopologyView nodes={snap.nodes} links={snap.links} highlightLinks={highlightedLinks} />
        ) : (
          <p className="empty">无节点数据</p>
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
        </h2>
        <table>
          <thead>
            <tr>
              <th>serviceId</th><th>类型</th><th>分类</th><th>src</th><th>dst</th>
              <th>优先级</th><th>状态</th><th>需求</th><th>路径</th><th>实测</th>
            </tr>
          </thead>
          <tbody>
            {sortedServices.map((s) => (
              <tr key={s.serviceId} className={s.status === "running" ? "running" : ""}>
                <td>{s.serviceId}</td>
                <td>{s.serviceType ?? "—"}</td>
                <td>
                  {s.category}
                  <small className="muted">({s.categorySource})</small>
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
                <td className="nowrap">
                  {s.actual
                    ? `D${s.actual.avgDelayMs ?? "—"} ${s.actual.qosMeet === true ? "✓" : s.actual.qosMeet === false ? "✗" : "?"}`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {snap && snap.services.length === 0 && <p className="empty">当前无业务（仿真尚未启动业务）</p>}
      </section>

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
    </section>
  );
}
