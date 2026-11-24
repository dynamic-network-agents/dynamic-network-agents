/**
 * 链路负载排行（需求侧）：按 demand/capacity 降序，前 8 条。
 *
 * `flowCount` 是结构量，不等于负载；`measuredBps` 是业务实测带宽汇总的**估计**，
 * 不是链路吞吐，因此不在此表展示为主指标。
 */
import { useMemo } from "react";
import type { LinkLoad, LinkRisk } from "../types";
import { mbps, pct } from "../lib/format";

interface Props {
  loads: LinkLoad[];
  risks: LinkRisk[];
  onSelectLink: (linkId: string) => void;
}

const LIMIT = 8;

export default function LinkLoadTable({ loads, risks, onSelectLink }: Props) {
  const byLink = useMemo(() => new Map(risks.map((r) => [r.linkId, r])), [risks]);
  const rows = useMemo(() => {
    const sorted = [...loads].sort((a, b) => {
      const ua = a.demandUtilization ?? null;
      const ub = b.demandUtilization ?? null;
      if (ua === null && ub === null) return b.demandBps - a.demandBps;
      if (ua === null) return 1;
      if (ub === null) return -1;
      return ub - ua;
    });
    return sorted.slice(0, LIMIT);
  }, [loads]);

  return (
    <section className="card" aria-label="链路负载">
      <div className="card-head">
        <div className="card-title">
          <h2>链路负载</h2>
          <span className="muted">需求 / 容量（估算）· 共 {loads.length} 条</span>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>链路</th>
              <th>需求 Mbps</th>
              <th>容量 Mbps</th>
              <th>需求/容量</th>
              <th>Flow/业务</th>
              <th>风险</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((l) => {
              const risk = byLink.get(l.linkId);
              const over = (l.demandUtilization ?? null) !== null && (l.demandUtilization ?? 0) > 1;
              return (
                <tr key={l.linkId} onClick={() => onSelectLink(l.linkId)}>
                  <td className="mono">{l.linkId}</td>
                  <td className="mono">{mbps(l.demandBps)}</td>
                  <td className="mono">{mbps(l.capacityBps)}</td>
                  <td className={`mono nowrap${over ? " bad" : ""}`}>
                    {pct(l.demandUtilization)}
                    {over && <small className="muted"> 超订</small>}
                  </td>
                  <td className="mono">
                    {l.flowCount} / {l.serviceCount}
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
      {rows.length === 0 && <p className="empty">无路径数据（业务未运行或路径未知）</p>}
      {loads.length > rows.length && (
        <p className="muted pad">显示前 {rows.length} 条，完整数据见「数据检查」。</p>
      )}
    </section>
  );
}
