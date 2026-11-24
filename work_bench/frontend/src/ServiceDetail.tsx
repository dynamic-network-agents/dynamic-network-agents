import type { Flow, Link, Service } from "./types";

interface Props {
  service: Service;
  flow?: Flow | null;
  linksById: Map<string, Link>;
  onSelectFlow: (flowKey: string) => void;
  onSelectLink: (linkId: string | null) => void;
  onClear: () => void;
}

function num(v: number | undefined | null, digits = 2): string {
  if (v === null || v === undefined) return "—";
  return Number(v).toFixed(digits);
}

/** Service 详情：需求 vs 实测（单位分开标注）、所属 Flow、路径链路。 */
export default function ServiceDetail({
  service,
  flow,
  linksById,
  onSelectFlow,
  onSelectLink,
  onClear,
}: Props) {
  const segments = service.path?.segments ?? [];
  const linkIds = segments.filter((s) => s.type === "link").map((s) => s.id);
  const req = service.requirement;
  const act = service.actual;

  return (
    <section className="panel" aria-label={`业务详情 ${service.serviceId}`}>
      <h2>
        业务详情：{service.serviceId}
        <button className="linkbtn" onClick={onClear} style={{ marginLeft: 12 }}>
          清除选择
        </button>
      </h2>

      <div className="detail-grid">
        <div>
          <span className="muted">类型/分类</span>
          <div>
            {service.serviceType ?? "—"} · {service.category ?? "unknown"}（
            {service.categorySource ?? "unknown"}）
          </div>
        </div>
        <div>
          <span className="muted">源 → 目的</span>
          <div>
            {service.srcNodeId ?? "—"} → {service.dstNodeId ?? "—"}
          </div>
        </div>
        <div>
          <span className="muted">优先级 / 状态</span>
          <div>
            {service.priority ?? "—"} / {service.status ?? "—"}
          </div>
        </div>
        <div>
          <span className="muted">所属 Flow</span>
          <div>
            {flow ? (
              <button className="linkbtn" onClick={() => onSelectFlow(flow.flowKey)}>
                {flow.flowKey}（{flow.memberCount} 条业务）
              </button>
            ) : (
              "unknown（无可用 IP 或业务未分组）"
            )}
          </div>
        </div>
        <div>
          <span className="muted">pathId</span>
          <div>{service.path?.pathId ?? "—"}</div>
        </div>
      </div>

      <h3>需求 vs 实测（单位不同，不合并判定）</h3>
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
            <td>{num(req?.delayMs)} ms</td>
            <td>{num(act?.avgDelayMs)} ms</td>
          </tr>
          <tr>
            <td>抖动</td>
            <td>{num(req?.jitterMs)} ms</td>
            <td>{num(act?.jitterMs)} ms</td>
          </tr>
          <tr>
            <td>带宽</td>
            <td>{num(req?.bandwidthBps, 0)} bps（下限）</td>
            <td>{num(act?.effBwBps, 0)} bps</td>
          </tr>
          <tr>
            <td>误码</td>
            <td>{req?.ber ?? "—"}（小数 0~1）</td>
            <td>{num(act?.errPct, 4)} %（百分数 0~100）</td>
          </tr>
          <tr>
            <td>丢包率</td>
            <td>{req?.packetLossRate ?? "—"}</td>
            <td>{act?.packetLossRate ?? "—"}</td>
          </tr>
          <tr>
            <td>综合</td>
            <td colSpan={2}>
              {act?.qosMeet === true ? "实测达标 ✓" : act?.qosMeet === false ? "实测不达标 ✗" : "unknown（无实测）"}
            </td>
          </tr>
        </tbody>
      </table>

      <h3>静态路径 QoS（链路参数合成，非实测）</h3>
      {service.staticQoS ? (
        <>
          <table>
            <thead>
              <tr>
                <th>指标</th>
                <th>静态合成值</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>时延 D=Σd</td><td>{num(service.staticQoS.delayMs)} ms</td></tr>
              <tr><td>抖动 J=√Σj²</td><td>{num(service.staticQoS.jitterMs)} ms</td></tr>
              <tr><td>带宽 B=min</td><td>{num(service.staticQoS.bandwidthBps, 0)} bps</td></tr>
              <tr><td>丢包 L=1−∏(1−p)</td><td>{service.staticQoS.packetLossRate ?? "—"}</td></tr>
              <tr><td>误码 E≈Σε</td><td>{service.staticQoS.ber ?? "—"}（小数）</td></tr>
            </tbody>
          </table>
          <p className="muted">
            容差：时延 +1.0ms、抖动/丢包 +1e-9、误码 +1e-12、带宽无容差；
            {service.staticQoS.missingParams.length > 0
              ? ` 缺参数：${service.staticQoS.missingParams.join(", ")}`
              : " 参数完整"}
          </p>
        </>
      ) : (
        <p className="empty">无路径或链路不在当前 /links，未做部分合成（避免把时延/带宽算低）</p>
      )}

      <h3>静态可行性</h3>
      {service.staticCheck ? (
        <div>
          <p className={service.staticCheck.ok === true ? "" : "bad"}>
            {service.staticCheck.ok === true
              ? "静态可行 ✓"
              : service.staticCheck.ok === false
                ? "静态不可行 ✗"
                : "unknown（缺参数或需求）"}
          </p>
          {service.staticCheck.violations.length > 0 && (
            <ul className="muted">
              {service.staticCheck.violations.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="muted">unknown（无静态合成或缺少链路参数）</p>
      )}

      <h3>当前路径链路（点击高亮单条）</h3>
      {linkIds.length === 0 ? (
        <p className="empty">无路径数据（业务未运行或路径未知）</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>linkId</th>
              <th>类型</th>
              <th>src → dst</th>
              <th>状态</th>
              <th>delayMs</th>
              <th>jitterMs</th>
              <th>带宽 bps</th>
              <th>ber</th>
              <th>丢包率</th>
            </tr>
          </thead>
          <tbody>
            {linkIds.map((id) => {
              const link = linksById.get(id);
              if (!link) {
                return (
                  <tr key={id}>
                    <td>{id}</td>
                    <td colSpan={8} className="bad">
                      不在当前 /links 中（可能已切除/删除）
                    </td>
                  </tr>
                );
              }
              return (
                <tr key={id} onClick={() => onSelectLink(id)} style={{ cursor: "pointer" }}>
                  <td>
                    <button className="linkbtn" onClick={() => onSelectLink(id)}>
                      {id}
                    </button>
                  </td>
                  <td>{link.linkType}</td>
                  <td>
                    {link.srcNodeId} → {link.dstNodeId}
                  </td>
                  <td className={link.status === "down" ? "bad" : ""}>{link.status ?? "—"}</td>
                  <td>{link.params?.delayMs ?? "—"}</td>
                  <td>{link.params?.jitterMs ?? "—"}</td>
                  <td>{link.params?.bandwidthBps ?? "—"}</td>
                  <td>{link.params?.ber ?? "—"}</td>
                  <td>{link.params?.packetLossRate ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
