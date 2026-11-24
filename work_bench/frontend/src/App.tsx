/**
 * 全局总览页（期 1）。
 *
 * 数据只有一个来源：`GET /api/snapshot`（2s 轮询，单飞请求）。页面不做二次计算，
 * 派生指标只在展示层做分组/排序，公式口径与后端 `analysis/` 对齐。
 *
 * 实例切换（instance_id 变化）时清空选中对象，避免不同实例的数据混在一个详情里。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchSnapshot } from "./api";
import type { Snapshot } from "./types";
import type { Selection } from "./lib/selection";
import { computeStats } from "./lib/derive";
import Sidebar, { type PageKey } from "./components/Sidebar";
import TopBar from "./components/TopBar";
import KpiCards from "./components/KpiCards";
import TopologyPanel from "./components/TopologyPanel";
import DiagnosticsPanel from "./components/DiagnosticsPanel";
import CriticalServicesTable from "./components/CriticalServicesTable";
import LinkLoadTable from "./components/LinkLoadTable";
import EventTimeline from "./components/EventTimeline";
import DetailDrawer from "./components/DetailDrawer";
import DataInspector from "./components/DataInspector";
import RepathPanel from "./components/RepathPanel";
import FlowAnalysisPage from "./components/FlowAnalysisPage";

const POLL_MS = 2000;

export default function App() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [page, setPage] = useState<PageKey>("overview");
  const instanceRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await fetchSnapshot();
      if (instanceRef.current && s.instance_id && s.instance_id !== instanceRef.current) {
        setSelection(null); // 实例切换：旧实例的选中对象不再有效
      }
      instanceRef.current = s.instance_id ?? instanceRef.current;
      setSnap(s);
      setLastUpdate(new Date());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    let inFlight = false;
    const tick = async () => {
      if (inFlight) return; // 上一轮未返回就跳过，避免请求叠加打挂上游
      inFlight = true;
      try {
        await load();
      } finally {
        inFlight = false;
      }
    };
    void tick();
    const id = setInterval(tick, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const stats = useMemo(() => computeStats(snap), [snap]);
  const flows = useMemo(() => snap?.flows ?? [], [snap]);
  const risks = useMemo(() => snap?.riskLinks ?? [], [snap]);
  const loads = useMemo(() => snap?.linkLoads ?? [], [snap]);

  const highlightLinks = useMemo(() => {
    const ids = new Set<string>();
    if (!selection) return ids;
    if (selection.kind === "link") {
      ids.add(selection.id);
    } else if (selection.kind === "service") {
      const svc = snap?.services.find((s) => s.serviceId === selection.id);
      for (const seg of svc?.path?.segments ?? []) {
        if (seg.type === "link") ids.add(seg.id);
      }
    } else if (selection.kind === "flow") {
      const flow = flows.find((f) => f.flowKey === selection.id);
      for (const lid of flow?.links ?? []) ids.add(lid);
    } else {
      for (const l of snap?.links ?? []) {
        if (l.srcNodeId === selection.id || l.dstNodeId === selection.id) ids.add(l.linkId);
      }
    }
    return ids;
  }, [selection, snap, flows]);

  const selectedNodeId = selection?.kind === "node" ? selection.id : null;
  const selectedLinkId = selection?.kind === "link" ? selection.id : null;

  const categoryTrusted = Boolean(snap?.svc_meta?.ok || snap?.offline);

  const select = useCallback((sel: Selection) => {
    setSelection((prev) => {
      if (prev && sel && prev.kind === sel.kind && prev.id === sel.id) return null; // 再点一次收起
      return sel;
    });
  }, []);

  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} />

      <div className="main">
        <TopBar snap={snap} error={error} lastUpdate={lastUpdate} />

        <main className="content">
          {!snap && !error && (
            <div className="loading" aria-live="polite">
              <p>正在连接工作台后端并采集第一份快照…</p>
              <div className="skeletons">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="skeleton" />
                ))}
              </div>
            </div>
          )}

          {!snap && error && (
            <div className="card error-state">
              <h2>无法获取快照</h2>
              <p className="mono">{error}</p>
              <p className="muted">
                检查后端是否启动（默认 127.0.0.1:8000），以及仿真器 API 是否可达。
              </p>
              <button type="button" className="btn" onClick={() => void load()}>
                立即重试
              </button>
            </div>
          )}

          {snap && page === "overview" && (
            <>
              <KpiCards snap={snap} stats={stats} />

              <div className="overview">
                <TopologyPanel
                  nodes={snap.nodes}
                  links={snap.links}
                  risks={risks}
                  highlightLinks={highlightLinks}
                  selectedNodeId={selectedNodeId}
                  selectedLinkId={selectedLinkId}
                  onSelectNode={(id) => select({ kind: "node", id })}
                  onSelectLink={(id) => select({ kind: "link", id })}
                  onClearSelection={() => setSelection(null)}
                />

                <DiagnosticsPanel
                  stats={stats}
                  risks={risks}
                  loads={loads}
                  categoryTrusted={categoryTrusted}
                  onSelectLink={(id) => select({ kind: "link", id })}
                />
              </div>

              <div className="rows">
                <CriticalServicesTable
                  services={snap.services}
                  flows={flows}
                  onSelectService={(id) => select({ kind: "service", id })}
                  onSelectFlow={(key) => select({ kind: "flow", id: key })}
                />
                <LinkLoadTable
                  loads={loads}
                  risks={risks}
                  onSelectLink={(id) => select({ kind: "link", id })}
                />
                <EventTimeline events={snap.events ?? []} />
              </div>

              <details className="card debug-card">
                <summary>
                  更改业务路径（唯一写接口 · 调试用）
                  <span className="muted"> · 默认经 WORKBENCH_ALLOW_REPATH 控制</span>
                </summary>
                <div className="card-body">
                  <RepathPanel services={snap.services} />
                </div>
              </details>

              <DataInspector snap={snap} lastUpdate={lastUpdate} error={error} />
            </>
          )}

          {snap && page === "flows" && (
            <FlowAnalysisPage
              snap={snap}
              onSelectService={(id) => select({ kind: "service", id })}
              onSelectLink={(id) => select({ kind: "link", id })}
            />
          )}
        </main>
      </div>

      <DetailDrawer
        selection={selection}
        snap={snap ?? emptySnapshot()}
        onClose={() => setSelection(null)}
        onSelect={(sel) => setSelection(sel)}
      />
    </div>
  );
}

/** 抽屉在无快照时不应渲染内容；给一个空壳避免空指针。 */
function emptySnapshot(): Snapshot {
  return {
    health: "disconnected",
    received_at: "",
    instance_id: null,
    scenario_id: null,
    sim_time_us: null,
    errors: [],
    nodes: [],
    links: [],
    services: [],
    events: [],
    events_cursor: 0,
  };
}
