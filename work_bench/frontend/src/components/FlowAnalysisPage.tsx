/**
 * 业务分析 · Flow 视图（期 2）。
 *
 * Flow 是路径控制对象（无序 IP 对），业务是它的成员；改一条业务路径 = 改整条 Flow。
 *
 * 页内口径：
 * - 当前路径参数来自实时 `/links`；风险来自 `riskLinks`；负载来自 `linkLoads`（需求侧估算）。
 * - 候选路径只来自离线 `service-paths.json`，静态可行性由后端按**当前**链路参数重算；
 *   文件里的 metrics 是计划期值，不展示。
 * - 候选对每个成员业务分别校验（成员需求可能不同），故有 ok/fail/unknown 三个计数。
 */
import { useEffect, useMemo, useState } from "react";
import { fetchFlowCandidates } from "../api";
import type {
  Flow,
  FlowCandidate,
  FlowCandidatesResponse,
  Link,
  LinkLoad,
  LinkRisk,
  Service,
  Snapshot,
} from "../types";
import { DASH, mbps, num, pct } from "../lib/format";

type FlowFilter = "all" | "bad" | "staticFail" | "discontinuous";

interface Props {
  snap: Snapshot;
  onSelectService: (serviceId: string) => void;
  onSelectLink: (linkId: string) => void;
}

function sci(v?: number | null): string {
  if (v === null || v === undefined) return DASH;
  return v === 0 ? "0" : v.toExponential(2);
}

export default function FlowAnalysisPage({ snap, onSelectService, onSelectLink }: Props) {
  const flows = snap.flows ?? [];
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FlowFilter>("all");
  const [selected, setSelected] = useState<string | null>(null);

  const activeKey = selected ?? flows[0]?.flowKey ?? null;
  const activeFlow = flows.find((f) => f.flowKey === activeKey) ?? null;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return flows
      .filter((f) => {
        if (filter === "bad" && f.qosMeetFalse === 0) return false;
        if (filter === "staticFail" && f.staticFailCount === 0) return false;
        if (filter === "discontinuous" && f.pathContinuous !== false) return false;
        if (!q) return true;
        const haystack = [
          f.flowKey,
          f.srcNodeId ?? "",
          f.dstNodeId ?? "",
          ...f.memberServiceIds,
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(q);
      })
      .sort(
        (a, b) =>
          b.qosMeetFalse - a.qosMeetFalse ||
          b.staticFailCount - a.staticFailCount ||
          b.memberCount - a.memberCount ||
          (a.flowKey < b.flowKey ? -1 : 1)
      );
  }, [flows, query, filter]);

  return (
    <div className="flow-page">
      <header className="page-head">
        <div>
          <h1>业务分析 · Flow 视图</h1>
          <p className="muted">
            Flow 是路径控制对象（无序 IP 对），业务是成员。改一条业务路径 = 改整条 Flow，影响全部成员。
          </p>
        </div>
        <span className="muted">
          {flows.length} 个 Flow · {snap.services.length} 条业务
        </span>
      </header>

      <div className="flow-layout">
        <section className="card flow-list-card" aria-label="Flow 列表">
          <div className="card-head">
            <div className="card-title">
              <h2>Flow 列表</h2>
              <span className="muted">
                {visible.length}/{flows.length}
              </span>
            </div>
          </div>

          <div className="list-tools">
            <input
              type="search"
              placeholder="搜索 flowKey / 节点 / 业务 ID"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="搜索 Flow"
            />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as FlowFilter)}
              aria-label="Flow 筛选"
            >
              <option value="all">全部</option>
              <option value="bad">有不达标成员</option>
              <option value="staticFail">静态有不可行</option>
              <option value="discontinuous">路径不连续</option>
            </select>
          </div>

          <ul className="flow-list">
            {visible.map((f) => (
              <li key={f.flowKey}>
                <button
                  type="button"
                  className={`flow-item${f.flowKey === activeKey ? " is-active" : ""}`}
                  onClick={() => setSelected(f.flowKey)}
                >
                  <span className="flow-key mono">{f.flowKey}</span>
                  <span className="flow-meta">
                    {f.srcNodeId ?? DASH} → {f.dstNodeId ?? DASH} · {f.memberCount} 成员
                  </span>
                  <span className="flow-chips">
                    {f.qosMeetFalse > 0 && <em className="bad">✗{f.qosMeetFalse}</em>}
                    {f.qosMeetUnknown > 0 && <em className="muted">?{f.qosMeetUnknown}</em>}
                    {f.qosMeetTrue > 0 && <em className="ok">✓{f.qosMeetTrue}</em>}
                    {f.staticFailCount > 0 && <em className="warn">静态✗{f.staticFailCount}</em>}
                    {f.pathContinuous === false && <em className="bad">不连续</em>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {visible.length === 0 && <p className="empty pad">没有匹配的 Flow</p>}
        </section>

        {activeFlow ? (
          <FlowDetail
            flow={activeFlow}
            snap={snap}
            onSelectService={onSelectService}
            onSelectLink={onSelectLink}
            onSelectFlow={setSelected}
          />
        ) : (
          <section className="card">
            <p className="empty pad">
              当前无 Flow：业务尚未启动，或节点没有可用 IP（无法推导无序 IP 对）。
            </p>
          </section>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 详情
function FlowDetail(props: {
  flow: Flow;
  snap: Snapshot;
  onSelectService: (serviceId: string) => void;
  onSelectLink: (linkId: string) => void;
  onSelectFlow: (flowKey: string) => void;
}) {
  const { flow, snap, onSelectService, onSelectLink, onSelectFlow } = props;

  const linksById = useMemo(
    () => new Map<string, Link>((snap.links ?? []).map((l) => [l.linkId, l])),
    [snap.links]
  );
  const loadsById = useMemo(
    () => new Map<string, LinkLoad>((snap.linkLoads ?? []).map((l) => [l.linkId, l])),
    [snap.linkLoads]
  );
  const risksById = useMemo(
    () => new Map<string, LinkRisk>((snap.riskLinks ?? []).map((r) => [r.linkId, r])),
    [snap.riskLinks]
  );

  const members = useMemo(
    () =>
      flow.memberServiceIds
        .map((id) => snap.services.find((s) => s.serviceId === id))
        .filter(Boolean) as Service[],
    [flow.memberServiceIds, snap.services]
  );

  const competitors = useMemo(() => {
    const m = new Map<string, Flow[]>();
    for (const lid of flow.links) {
      m.set(
        lid,
        (snap.flows ?? []).filter((f) => f.flowKey !== flow.flowKey && f.links.includes(lid))
      );
    }
    return m;
  }, [flow, snap.flows]);

  return (
    <div className="flow-detail">
      <section className="card">
        <div className="card-head">
          <div className="card-title">
            <h2 className="mono">{flow.flowKey}</h2>
            <span className="muted">
              {flow.srcNodeId ?? DASH} → {flow.dstNodeId ?? DASH} · {flow.memberCount} 成员 ·{" "}
              {flow.direction ?? DASH}
            </span>
          </div>
          <div className="flow-chips">
            <span className="chip chip-sm tone-bad">不达标 {flow.qosMeetFalse}</span>
            <span className="chip chip-sm tone-idle">未知 {flow.qosMeetUnknown}</span>
            <span className="chip chip-sm tone-ok">达标 {flow.qosMeetTrue}</span>
          </div>
        </div>

        <div className="card-body">
          <div className="dr-grid cols-3">
            <div className="dr">
              <span className="dr-k">源 / 目的 IP</span>
              <span className="dr-v mono">
                {flow.srcIp ?? DASH} → {flow.dstIp ?? DASH}
              </span>
            </div>
            <div className="dr">
              <span className="dr-k">pathId</span>
              <span className="dr-v mono">{flow.pathId ?? DASH}</span>
            </div>
            <div className="dr">
              <span className="dr-k">路径连续性</span>
              <span className="dr-v">
                {flow.pathContinuous === true
                  ? "连续"
                  : flow.pathContinuous === false
                    ? `不连续（缺 ${(flow.missingLinks ?? []).join(", ")}）`
                    : DASH}
              </span>
            </div>
            <div className="dr">
              <span className="dr-k">静态可行性（成员）</span>
              <span className="dr-v">
                可行 {flow.staticOkCount} · 不可行 {flow.staticFailCount} · 未知{" "}
                {flow.staticUnknownCount}
              </span>
            </div>
            <div className="dr">
              <span className="dr-k">分类构成</span>
              <span className="dr-v">
                {Object.entries(flow.categoryCounts ?? {})
                  .map(([k, v]) => `${k}×${v}`)
                  .join("  ") || DASH}
              </span>
            </div>
            <div className="dr">
              <span className="dr-k">路径段数</span>
              <span className="dr-v mono">{flow.links.length}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div className="card-title">
            <h2>当前路径</h2>
            <span className="muted">参数取自实时 /links；风险来自规则 A</span>
          </div>
        </div>
        {flow.links.length === 0 ? (
          <p className="empty pad">无路径数据（业务未运行或路径未知）。</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>链路</th>
                  <th>端点</th>
                  <th>状态</th>
                  <th>时延 ms</th>
                  <th>抖动 ms</th>
                  <th>带宽</th>
                  <th>丢包</th>
                  <th>需求/容量</th>
                  <th>风险</th>
                </tr>
              </thead>
              <tbody>
                {flow.links.map((lid) => {
                  const link = linksById.get(lid);
                  const load = loadsById.get(lid);
                  const risk = risksById.get(lid);
                  return (
                    <tr key={lid} onClick={() => onSelectLink(lid)}>
                      <td className="mono">{lid}</td>
                      <td className="mono nowrap">
                        {link ? `${link.srcNodeId} → ${link.dstNodeId}` : "不在 /links"}
                      </td>
                      <td className={link?.status === "down" ? "bad" : ""}>
                        {link?.status ?? DASH}
                      </td>
                      <td className="mono">{num(link?.params?.delayMs, 1)}</td>
                      <td className="mono">{num(link?.params?.jitterMs, 1)}</td>
                      <td className="mono">{mbps(link?.params?.bandwidthBps)} Mbps</td>
                      <td className="mono">{num(link?.params?.packetLossRate, 4)}</td>
                      <td className={`mono${(load?.demandUtilization ?? 0) > 1 ? " bad" : ""}`}>
                        {pct(load?.demandUtilization)}
                      </td>
                      <td>
                        {risk ? (
                          <span className={`sev sev-${risk.severity}`}>{risk.codes.join(" ")}</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <div className="card-title">
            <h2>成员业务</h2>
            <span className="muted">{members.length} 条共享该路径</span>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>业务</th>
                <th>分类</th>
                <th>优先级</th>
                <th>QoS（实测）</th>
                <th>需求时延</th>
                <th>实测时延</th>
                <th>需求带宽</th>
                <th>静态</th>
              </tr>
            </thead>
            <tbody>
              {members.map((s) => (
                <tr key={s.serviceId} onClick={() => onSelectService(s.serviceId)}>
                  <td className="mono">{s.serviceId}</td>
                  <td>
                    <span className={`cat cat-${s.category ?? "unknown"}`}>
                      {s.category ?? "unknown"}
                    </span>
                  </td>
                  <td className="mono">{s.priority ?? DASH}</td>
                  <td>
                    {s.actual?.qosMeet === true
                      ? "达标"
                      : s.actual?.qosMeet === false
                        ? <span className="bad">不达标</span>
                        : "未知"}
                  </td>
                  <td className="mono">{num(s.requirement?.delayMs, 1)} ms</td>
                  <td className="mono">{num(s.actual?.avgDelayMs, 1)} ms</td>
                  <td className="mono">{mbps(s.requirement?.bandwidthBps)} Mbps</td>
                  <td>
                    {s.staticCheck?.ok === true
                      ? "可行"
                      : s.staticCheck?.ok === false
                        ? <span className="bad">不可行</span>
                        : "未知"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {flow.links.length > 0 && (
        <section className="card">
          <div className="card-head">
            <div className="card-title">
              <h2>链路上的其他 Flow</h2>
              <span className="muted">同一段链路被多个 Flow 共享时，改路径会互相影响</span>
            </div>
          </div>
          <div className="card-body">
            <ul className="plain-list">
              {flow.links.map((lid) => {
                const others = competitors.get(lid) ?? [];
                return (
                  <li key={lid}>
                    <span className="mono">{lid}</span>
                    <span className="muted"> · </span>
                    {others.length === 0 ? (
                      <span className="muted">无其他 Flow</span>
                    ) : (
                      others.map((f) => (
                        <button
                          key={f.flowKey}
                          type="button"
                          className="linkbtn"
                          onClick={() => onSelectFlow(f.flowKey)}
                        >
                          {f.flowKey}（{f.memberCount}）{" "}
                        </button>
                      ))
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      )}

      <CandidateSection
        flowKey={flow.flowKey}
        onSelectService={onSelectService}
      />
    </div>
  );
}

// ---------------------------------------------------------------- 候选路径
function CandidateSection(props: {
  flowKey: string;
  onSelectService: (serviceId: string) => void;
}) {
  const { flowKey, onSelectService } = props;
  const [data, setData] = useState<FlowCandidatesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    setLoading(true);
    fetchFlowCandidates(flowKey)
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [flowKey, reload]);

  return (
    <section className="card">
      <div className="card-head">
        <div className="card-title">
          <h2>候选路径与静态可行性</h2>
          <span className="muted">
            候选来自离线 service-paths.json，静态值按当前链路参数重算（不是实测）
          </span>
        </div>
        <div className="cand-head-tools">
          {data && <span className="muted">{data.candidates.length} 条</span>}
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setReload((n) => n + 1)}
            disabled={loading}
          >
            {loading ? "读取中…" : "刷新"}
          </button>
        </div>
      </div>

      <div className="card-body">
        {loading && <p className="empty">正在读取候选路径…</p>}
        {error && <p className="bad">候选路径读取失败：{error}</p>}
        {data?.note && <p className="warn">{data.note}</p>}

        {data && data.candidates.length > 0 && (
          <div className="cand-list">
            {data.candidates.map((c) => (
              <CandidateCard key={c.candidateId} candidate={c} onSelectService={onSelectService} />
            ))}
          </div>
        )}

        <p className="muted">
          静态可行 ≠ 实测达标：静态是按链路参数合成的上限校验，实测是逐秒统计（qosMeet）。
          静态值基于后端最近一次快照的链路参数；链路参数变化后请点「刷新」重取。
        </p>
      </div>
    </section>
  );
}

function CandidateCard(props: {
  candidate: FlowCandidate;
  onSelectService: (serviceId: string) => void;
}) {
  const { candidate: c, onSelectService } = props;
  const violations = c.perMember.filter((m) => m.violations.length > 0);

  return (
    <article className={`cand${c.isCurrent ? " is-current" : ""}`}>
      <header className="cand-head">
        <b className="mono">{c.candidateId}</b>
        {c.isCurrent && <span className="tag">当前路径</span>}
        {c.pathNo != null && <span className="muted mono">pathNo {c.pathNo}</span>}
        <span className="muted">
          {c.linkCount} 段 · 覆盖 {c.serviceIds.length} 个成员
        </span>
      </header>

      <div className="mono cand-links">{c.links.join(" → ")}</div>

      {c.staticQoS ? (
        <div className="cand-qos mono">
          <span>D {num(c.staticQoS.delayMs, 1)}ms</span>
          <span>J {num(c.staticQoS.jitterMs, 1)}ms</span>
          <span>B {mbps(c.staticQoS.bandwidthBps)}Mbps</span>
          <span>L {num(c.staticQoS.packetLossRate, 4)}</span>
          <span>E {sci(c.staticQoS.ber)}</span>
        </div>
      ) : (
        <p className="bad">候选链路不在当前 /links：{c.missingLinks.join(", ") || DASH}</p>
      )}

      <div className="cand-checks">
        <span className="ok">可行 {c.checks.ok}</span>
        <span className="bad">不可行 {c.checks.fail}</span>
        <span className="muted">未知 {c.checks.unknown}</span>
      </div>

      {violations.length > 0 && (
        <details className="cand-violations">
          <summary>逐成员校验（{violations.length} 条有冲突）</summary>
          <ul className="plain-list">
            {violations.map((m) => (
              <li key={m.serviceId}>
                <button
                  type="button"
                  className="linkbtn mono"
                  onClick={() => onSelectService(m.serviceId)}
                >
                  {m.serviceId}
                </button>
                <ul>
                  {m.violations.map((v) => (
                    <li key={v} className="muted">
                      {v}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
