/**
 * 详情抽屉：Service / Flow / Link 三类对象共用。
 *
 * 口径：
 * - 需求（上限）与实测分开列，单位分别标注；`errPct` 是百分数，`requirement.ber` 是小数；
 * - 静态 QoS 是**路径估算**，`qosMeet` 是**业务实测**，两者不一致时明确标注；
 * - 缺失值显示「—」，不做 0 填充。
 */
import type { Flow, Link, LinkLoad, LinkRisk, Node, Service, SimEvent, Snapshot } from "../types";
import type { Selection } from "../lib/selection";
import { num, mbps, pct, segIds, DASH } from "../lib/format";

interface Props {
  selection: Selection;
  snap: Snapshot;
  onClose: () => void;
  onSelect: (sel: DrawerSelection) => void;
}

/** 只允许选择业务/Flow/链路，避免抽屉里再开抽屉。 */
type DrawerSelection = Exclude<Selection, null>;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="dr">
      <span className="dr-k">{label}</span>
      <span className="dr-v">{children}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="dr-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export default function DetailDrawer({ selection, snap, onClose, onSelect }: Props) {
  if (!selection) return null;

  const servicesById = new Map((snap.services ?? []).map((s) => [s.serviceId, s]));
  const linksById = new Map((snap.links ?? []).map((l) => [l.linkId, l]));
  const nodesById = new Map((snap.nodes ?? []).map((n) => [n.nodeId, n]));
  const loadsById = new Map((snap.linkLoads ?? []).map((l) => [l.linkId, l]));
  const risksById = new Map((snap.riskLinks ?? []).map((r) => [r.linkId, r]));
  const flows = snap.flows ?? [];

  let title = "";
  let body: React.ReactNode = null;

  if (selection.kind === "service") {
    const svc = servicesById.get(selection.id);
    if (!svc) {
      body = <p className="empty">该业务不在当前快照（可能已结束或分页未覆盖）。</p>;
    } else {
      title = `业务 ${svc.serviceId}`;
      const flow = flows.find((f) => f.memberServiceIds.includes(svc.serviceId)) ?? null;
      body = (
        <ServiceView
          service={svc}
          flow={flow}
          linksById={linksById}
          risksById={risksById}
          onSelect={onSelect}
        />
      );
    }
  } else if (selection.kind === "flow") {
    const flow = flows.find((f) => f.flowKey === selection.id);
    if (!flow) {
      body = <p className="empty">该 Flow 不在当前快照。</p>;
    } else {
      title = `Flow ${flow.flowKey}`;
      body = (
        <FlowView
          flow={flow}
          services={flow.memberServiceIds.map((id) => servicesById.get(id)).filter(Boolean) as Service[]}
          linksById={linksById}
          loadsById={loadsById}
          risksById={risksById}
          flows={flows}
          onSelect={onSelect}
        />
      );
    }
  } else if (selection.kind === "link") {
    const link = linksById.get(selection.id);
    if (!link) {
      body = <p className="empty">该链路不在当前快照（可能已切除）。</p>;
    } else {
      title = `链路 ${link.linkId}`;
      body = (
        <LinkView
          link={link}
          load={loadsById.get(link.linkId) ?? null}
          risk={risksById.get(link.linkId) ?? null}
          flows={flows}
          servicesById={servicesById}
          events={snap.events ?? []}
          onSelect={onSelect}
        />
      );
    }
  } else {
    const node = nodesById.get(selection.id);
    if (!node) {
      body = <p className="empty">该节点不在当前快照。</p>;
    } else {
      title = `节点 ${node.nodeId}`;
      body = (
        <NodeView
          node={node}
          links={(snap.links ?? []).filter(
            (l) => l.srcNodeId === node.nodeId || l.dstNodeId === node.nodeId
          )}
          services={(snap.services ?? []).filter(
            (s) => s.srcNodeId === node.nodeId || s.dstNodeId === node.nodeId
          )}
          onSelect={onSelect}
        />
      );
    }
  }

  return (
    <div className="drawer" role="dialog" aria-modal="false" aria-label={title}>
      <div className="drawer-head">
        <h2>{title}</h2>
        <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="关闭详情">
          关闭
        </button>
      </div>
      <div className="drawer-body">{body}</div>
    </div>
  );
}

// ---------------------------------------------------------------- Service
function ServiceView(props: {
  service: Service;
  flow: Flow | null;
  linksById: Map<string, Link>;
  risksById: Map<string, LinkRisk>;
  onSelect: (sel: DrawerSelection) => void;
}) {
  const { service, flow, linksById, risksById, onSelect } = props;
  const req = service.requirement;
  const act = service.actual;
  const linkIds = (service.path?.segments ?? []).filter((s) => s.type === "link").map((s) => s.id);

  return (
    <>
      <Section title="基本信息">
        <div className="dr-grid">
          <Row label="类型 / 分类">
            {service.serviceType ?? DASH} · {service.category ?? "unknown"}
            <small className="muted">（{service.categorySource ?? "unknown"}）</small>
          </Row>
          <Row label="源 → 目的">
            {service.srcNodeId ?? DASH} → {service.dstNodeId ?? DASH}
          </Row>
          <Row label="优先级 / 状态">
            {service.priority ?? DASH} / {service.status ?? DASH}
          </Row>
          <Row label="pathId">{service.path?.pathId ?? DASH}</Row>
          <Row label="所属 Flow">
            {flow ? (
              <button type="button" className="linkbtn" onClick={() => onSelect({ kind: "flow", id: flow.flowKey })}>
                {flow.flowKey}
              </button>
            ) : (
              "unknown（无可用 IP 或业务未分组）"
            )}
            {flow && <small className="muted"> · 共享 {flow.memberCount} 条业务</small>}
          </Row>
        </div>
        {service.detailError && <p className="bad">详情拉取失败：{service.detailError}</p>}
      </Section>

      <Section title="需求 vs 实测（单位不同，分别判定）">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>指标</th>
                <th>需求（上限/下限）</th>
                <th>实测</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>时延</td>
                <td className="mono">{num(req?.delayMs)} ms</td>
                <td className="mono">{num(act?.avgDelayMs)} ms</td>
              </tr>
              <tr>
                <td>抖动</td>
                <td className="mono">{num(req?.jitterMs)} ms</td>
                <td className="mono">{num(act?.jitterMs)} ms</td>
              </tr>
              <tr>
                <td>带宽</td>
                <td className="mono">{num(req?.bandwidthBps, 0)} bps（下限）</td>
                <td className="mono">{num(act?.effBwBps, 0)} bps</td>
              </tr>
              <tr>
                <td>误码</td>
                <td className="mono">{req?.ber ?? DASH}（小数 0~1）</td>
                <td className="mono">{num(act?.errPct, 4)} %（百分数 0~100）</td>
              </tr>
              <tr>
                <td>丢包率</td>
                <td className="mono">{req?.packetLossRate ?? DASH}</td>
                <td className="mono">{act?.packetLossRate ?? DASH}</td>
              </tr>
              <tr>
                <td>综合（qosMeet）</td>
                <td colSpan={2}>
                  {act?.qosMeet === true
                    ? "实测达标"
                    : act?.qosMeet === false
                      ? "实测不达标"
                      : "unknown（无实测）"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="静态路径 QoS（链路参数合成，非实测）">
        {service.staticQoS ? (
          <>
            <div className="dr-grid">
              <Row label="时延 D=Σd">{num(service.staticQoS.delayMs)} ms</Row>
              <Row label="抖动 J=√Σj²">{num(service.staticQoS.jitterMs)} ms</Row>
              <Row label="带宽 B=min">{num(service.staticQoS.bandwidthBps, 0)} bps</Row>
              <Row label="丢包 L=1−∏(1−p)">{service.staticQoS.packetLossRate ?? DASH}</Row>
              <Row label="误码 E≈Σε">{service.staticQoS.ber ?? DASH}</Row>
              <Row label="静态可行性">
                {service.staticCheck?.ok === true
                  ? "可行"
                  : service.staticCheck?.ok === false
                    ? "不可行"
                    : "unknown"}
                {service.staticCheck?.ok === false && act?.qosMeet === true && (
                  <small className="warn"> 静态不可行但实测达标（容差/时序差异）</small>
                )}
                {service.staticCheck?.ok === true && act?.qosMeet === false && (
                  <small className="bad"> 静态可行但实测不达标（运行时拥塞/竞争）</small>
                )}
              </Row>
            </div>
            {service.staticQoS.missingParams.length > 0 && (
              <p className="warn">缺参数：{service.staticQoS.missingParams.join(", ")}</p>
            )}
            {service.staticCheck?.violations?.length ? (
              <ul className="muted">
                {service.staticCheck.violations.map((v) => (
                  <li key={v}>{v}</li>
                ))}
              </ul>
            ) : null}
          </>
        ) : (
          <p className="empty">无路径或链路不在当前 /links，未做部分合成（避免把时延/带宽算低）</p>
        )}
      </Section>

      <Section title={`当前路径（${linkIds.length} 段）`}>
        {linkIds.length === 0 ? (
          <p className="empty">无路径数据（业务未运行或路径未知）</p>
        ) : (
          <div className="chips">
            {linkIds.map((id) => {
              const link = linksById.get(id);
              const risk = risksById.get(id);
              return (
                <button
                  key={id}
                  type="button"
                  className={`chip-link${risk ? " is-risk" : ""}`}
                  onClick={() => onSelect({ kind: "link", id })}
                  title={link ? `${link.srcNodeId} → ${link.dstNodeId}` : "不在当前 /links"}
                >
                  {id}
                  {risk && <em>{risk.codes.join("")}</em>}
                </button>
              );
            })}
          </div>
        )}
        <p className="muted">路径段只含链路；顺序取决于最近一次下发方向（可能是反序）。</p>
      </Section>
    </>
  );
}

// ---------------------------------------------------------------- Flow
function FlowView(props: {
  flow: Flow;
  services: Service[];
  linksById: Map<string, Link>;
  loadsById: Map<string, LinkLoad>;
  risksById: Map<string, LinkRisk>;
  flows: Flow[];
  onSelect: (sel: DrawerSelection) => void;
}) {
  const { flow, services, linksById, loadsById, risksById, flows, onSelect } = props;

  const competitors = new Map<string, Flow[]>();
  for (const lid of flow.links) {
    competitors.set(
      lid,
      flows.filter((f) => f.flowKey !== flow.flowKey && f.links.includes(lid))
    );
  }

  return (
    <>
      <Section title="基本信息">
        <div className="dr-grid">
          <Row label="flowKey（推导）">
            <span className="mono">{flow.flowKey}</span>
          </Row>
          <Row label="源 → 目的">
            {flow.srcNodeId ?? DASH} → {flow.dstNodeId ?? DASH}
            <small className="muted">
              {flow.srcIp ?? DASH} / {flow.dstIp ?? DASH}
            </small>
          </Row>
          <Row label="成员业务">{flow.memberCount}</Row>
          <Row label="pathId">{flow.pathId ?? DASH}</Row>
          <Row label="路径方向">{flow.direction ?? DASH}</Row>
          <Row label="路径连续性">
            {flow.pathContinuous === true ? "连续" : flow.pathContinuous === false ? "不连续" : DASH}
            {(flow.missingLinks?.length ?? 0) > 0 && (
              <small className="bad"> 缺 {flow.missingLinks?.join(", ")}</small>
            )}
          </Row>
        </div>
        <p className="muted">
          同一对源/目的（无序 IP 对）共用一条 flow 级路径；改一条业务 = 改整条路径，影响全部成员。
        </p>
      </Section>

      <Section title={`路径链路（${flow.links.length}）`}>
        {flow.links.length === 0 ? (
          <p className="empty">无路径数据</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>链路</th>
                  <th>端点</th>
                  <th>状态</th>
                  <th>需求/容量</th>
                  <th>其他 Flow</th>
                </tr>
              </thead>
              <tbody>
                {flow.links.map((lid) => {
                  const link = linksById.get(lid);
                  const load = loadsById.get(lid);
                  const risk = risksById.get(lid);
                  const others = competitors.get(lid) ?? [];
                  return (
                    <tr key={lid} onClick={() => onSelect({ kind: "link", id: lid })}>
                      <td className="mono">
                        {lid}
                        {risk && <span className={`sev sev-${risk.severity}`}> {risk.severity}</span>}
                      </td>
                      <td className="mono nowrap">
                        {link ? `${link.srcNodeId} → ${link.dstNodeId}` : "不在 /links"}
                      </td>
                      <td>{link?.status ?? DASH}</td>
                      <td className={`mono${(load?.demandUtilization ?? 0) > 1 ? " bad" : ""}`}>
                        {pct(load?.demandUtilization)}
                      </td>
                      <td>{others.length}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={`成员业务（${services.length}）`}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>业务</th>
                <th>分类</th>
                <th>优先级</th>
                <th>QoS</th>
                <th>时延</th>
              </tr>
            </thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.serviceId} onClick={() => onSelect({ kind: "service", id: s.serviceId })}>
                  <td className="mono">{s.serviceId}</td>
                  <td>{s.category ?? "unknown"}</td>
                  <td className="mono">{s.priority ?? DASH}</td>
                  <td>
                    {s.actual?.qosMeet === true
                      ? "达标"
                      : s.actual?.qosMeet === false
                        ? "不达标"
                        : "未知"}
                  </td>
                  <td className="mono">{num(s.actual?.avgDelayMs)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="静态路径 QoS（该 Flow 代表路径）">
        {flow.staticQoS ? (
          <div className="dr-grid">
            <Row label="时延">{num(flow.staticQoS.delayMs)} ms</Row>
            <Row label="抖动">{num(flow.staticQoS.jitterMs)} ms</Row>
            <Row label="带宽">{num(flow.staticQoS.bandwidthBps, 0)} bps</Row>
            <Row label="丢包">{flow.staticQoS.packetLossRate ?? DASH}</Row>
            <Row label="误码">{flow.staticQoS.ber ?? DASH}</Row>
            <Row label="成员静态可行性">
              可行 {flow.staticOkCount} / 不可行 {flow.staticFailCount} / 未知 {flow.staticUnknownCount}
            </Row>
          </div>
        ) : (
          <p className="empty">链路参数不全，未做静态合成</p>
        )}
      </Section>
    </>
  );
}

// ---------------------------------------------------------------- Link
function LinkView(props: {
  link: Link;
  load: LinkLoad | null;
  risk: LinkRisk | null;
  flows: Flow[];
  servicesById: Map<string, Service>;
  events: SimEvent[];
  onSelect: (sel: DrawerSelection) => void;
}) {
  const { link, load, risk, flows, servicesById, events, onSelect } = props;

  const usingFlows = flows.filter((f) => f.links.includes(link.linkId));
  const memberIds = Array.from(new Set(usingFlows.flatMap((f) => f.memberServiceIds)));
  const memberServices = memberIds.map((id) => servicesById.get(id)).filter(Boolean) as Service[];
  const relatedEvents = events.filter(
    (e) => (e.payload as Record<string, unknown> | undefined)?.linkId === link.linkId
  );

  return (
    <>
      <Section title="链路参数">
        <div className="dr-grid">
          <Row label="端点">
            {link.srcNodeId} → {link.dstNodeId}
          </Row>
          <Row label="类型 / 状态">
            {link.linkType ?? DASH} / {link.status ?? DASH}
          </Row>
          <Row label="时延">{num(link.params?.delayMs)} ms</Row>
          <Row label="抖动">{num(link.params?.jitterMs)} ms</Row>
          <Row label="带宽">{num(link.params?.bandwidthBps, 0)} bps</Row>
          <Row label="误码 ber">{link.params?.ber ?? DASH}</Row>
          <Row label="丢包率">{link.params?.packetLossRate ?? DASH}</Row>
        </div>
      </Section>

      {risk && (
        <Section title="风险判定（规则 A）">
          <p>
            <span className={`sev sev-${risk.severity}`}>{risk.severity}</span>{" "}
            {risk.codes.join(" · ")}
            {risk.isEstimated && <span className="tag">含估算项</span>}
          </p>
          <ul className="muted">
            {risk.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="需求侧负载（估算）">
        {load ? (
          <div className="dr-grid">
            <Row label="需求带宽">{mbps(load.demandBps)} Mbps</Row>
            <Row label="容量">{mbps(load.capacityBps)} Mbps</Row>
            <Row label="需求/容量">
              <span className={(load.demandUtilization ?? 0) > 1 ? "bad" : ""}>
                {pct(load.demandUtilization)}
              </span>
            </Row>
            <Row label="Flow / 业务">
              {load.flowCount} / {load.serviceCount}
            </Row>
            <Row label="实测汇总（估计）">
              {mbps(load.measuredBps)} Mbps
              <small className="muted"> 业务实测带宽汇总，不是链路吞吐</small>
            </Row>
          </div>
        ) : (
          <p className="empty">该链路没有承载业务（或路径未知）</p>
        )}
      </Section>

      <Section title={`经过的 Flow（${usingFlows.length}）`}>
        {usingFlows.length === 0 ? (
          <p className="empty">无</p>
        ) : (
          <ul className="plain-list">
            {usingFlows.map((f) => (
              <li key={f.flowKey}>
                <button type="button" className="linkbtn" onClick={() => onSelect({ kind: "flow", id: f.flowKey })}>
                  {f.flowKey}
                </button>
                <span className="muted"> · {f.memberCount} 条业务</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={`受影响业务（${memberServices.length}）`}>
        {memberServices.length === 0 ? (
          <p className="empty">无</p>
        ) : (
          <div className="chips">
            {memberServices.map((s) => (
              <button
                key={s.serviceId}
                type="button"
                className={`chip-link${s.actual?.qosMeet === false ? " is-bad" : ""}`}
                onClick={() => onSelect({ kind: "service", id: s.serviceId })}
              >
                {s.serviceId}
              </button>
            ))}
          </div>
        )}
        <p className="muted">路径段：{segIds(usingFlows[0]?.links.map((id) => ({ type: "link", id })) ?? null)}</p>
      </Section>

      <Section title={`相关事件（${relatedEvents.length}）`}>
        {relatedEvents.length === 0 ? (
          <p className="empty">无该链路事件</p>
        ) : (
          <ul className="plain-list">
            {relatedEvents.map((e) => (
              <li key={e.eventId} className="mono">
                {e.type} · {e.time ?? DASH}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </>
  );
}


// ---------------------------------------------------------------- Node
function NodeView(props: {
  node: Node;
  links: Link[];
  services: Service[];
  onSelect: (sel: DrawerSelection) => void;
}) {
  const { node, links, services, onSelect } = props;
  const bad = services.filter((s) => s.actual?.qosMeet === false);

  return (
    <>
      <Section title="节点信息">
        <div className="dr-grid">
          <Row label="nodeId">{node.nodeId}</Row>
          <Row label="名称">{node.name ?? DASH}</Row>
          <Row label="类型">{node.nodeType ?? DASH}</Row>
          <Row label="状态">{node.status ?? DASH}</Row>
          <Row label="IP / 掩码">
            {node.ip ?? DASH}
            {node.mask ? ` / ${node.mask}` : ""}
          </Row>
          <Row label="坐标">
            {node.position ? `${node.position.x.toFixed(0)}, ${node.position.y.toFixed(0)}` : "缺坐标（布局估算）"}
          </Row>
        </div>
      </Section>

      <Section title={`直连链路（${links.length}）`}>
        {links.length === 0 ? (
          <p className="empty">无直连链路</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>链路</th>
                  <th>端点</th>
                  <th>状态</th>
                  <th>时延</th>
                  <th>带宽</th>
                </tr>
              </thead>
              <tbody>
                {links.map((l) => (
                  <tr key={l.linkId} onClick={() => onSelect({ kind: "link", id: l.linkId })}>
                    <td className="mono">{l.linkId}</td>
                    <td className="mono nowrap">
                      {l.srcNodeId} → {l.dstNodeId}
                    </td>
                    <td className={l.status === "down" ? "bad" : ""}>{l.status ?? DASH}</td>
                    <td className="mono">{num(l.params?.delayMs)} ms</td>
                    <td className="mono">{num(l.params?.bandwidthBps, 0)} bps</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={`端点业务（${services.length}）`}>
        {services.length === 0 ? (
          <p className="empty">该节点没有业务端点</p>
        ) : (
          <div className="chips">
            {services.map((s) => (
              <button
                key={s.serviceId}
                type="button"
                className={`chip-link${s.actual?.qosMeet === false ? " is-bad" : ""}`}
                onClick={() => onSelect({ kind: "service", id: s.serviceId })}
              >
                {s.serviceId}
              </button>
            ))}
          </div>
        )}
        {bad.length > 0 && <p className="bad">{bad.length} 条端点业务实测不达标</p>}
      </Section>
    </>
  );
}
