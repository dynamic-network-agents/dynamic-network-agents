/**
 * 关键业务表：默认按「不达标 → 未知 → 达标、优先级降序」排列，最多 12 行。
 * 点击行打开 Service 抽屉；Flow 列可单独下钻到 Flow。
 */
import { useMemo, useState } from "react";
import type { Flow, Service } from "../types";
import { sortServicesForTriage } from "../lib/derive";
import { num } from "../lib/format";

interface Props {
  services: Service[];
  flows: Flow[];
  onSelectService: (serviceId: string) => void;
  onSelectFlow: (flowKey: string) => void;
}

type Filter = "all" | "bad" | "unknown";

const LIMIT = 12;

function QosChip({ meet }: { meet?: boolean }) {
  if (meet === true) return <span className="chip chip-sm tone-ok">达标</span>;
  if (meet === false) return <span className="chip chip-sm tone-bad">不达标</span>;
  return <span className="chip chip-sm tone-idle">未知</span>;
}

export default function CriticalServicesTable({
  services,
  flows,
  onSelectService,
  onSelectFlow,
}: Props) {
  const [filter, setFilter] = useState<Filter>("all");

  const flowByService = useMemo(() => {
    const m = new Map<string, Flow>();
    for (const f of flows) for (const sid of f.memberServiceIds) m.set(sid, f);
    return m;
  }, [flows]);

  const rows = useMemo(() => {
    const filtered = services.filter((s) => {
      if (filter === "bad") return s.actual?.qosMeet === false;
      if (filter === "unknown") return s.actual?.qosMeet == null;
      return true;
    });
    return sortServicesForTriage(filtered).slice(0, LIMIT);
  }, [services, filter]);

  const badCount = services.filter((s) => s.actual?.qosMeet === false).length;
  const unknownCount = services.filter((s) => s.actual?.qosMeet == null).length;

  return (
    <section className="card" aria-label="关键业务">
      <div className="card-head">
        <div className="card-title">
          <h2>关键业务</h2>
          <span className="muted">
            不达标 {badCount} · 未知 {unknownCount} · 共 {services.length}
          </span>
        </div>
        <div className="segmented" role="group" aria-label="业务筛选">
          {(
            [
              ["all", "全部"],
              ["bad", "不达标"],
              ["unknown", "未知"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`seg${filter === key ? " is-active" : ""}`}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业务</th>
              <th>Flow</th>
              <th>分类</th>
              <th>源 → 目的</th>
              <th>QoS</th>
              <th>时延 / 抖动</th>
              <th>路径</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const flow = flowByService.get(s.serviceId);
              return (
                <tr key={s.serviceId} onClick={() => onSelectService(s.serviceId)}>
                  <td className="mono">{s.serviceId}</td>
                  <td>
                    {flow ? (
                      <>
                      <button
                        type="button"
                        className="linkbtn trunc"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectFlow(flow.flowKey);
                        }}
                        title={`${flow.flowKey} · ${flow.memberCount} 条成员业务共享该路径`}
                      >
                        {flow.flowKey}
                      </button>
                      <small className="muted"> ×{flow.memberCount}</small>
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>
                    <span className={`cat cat-${s.category ?? "unknown"}`}>{s.category ?? "unknown"}</span>
                  </td>
                  <td className="mono nowrap">
                    {s.srcNodeId ?? "—"} → {s.dstNodeId ?? "—"}
                  </td>
                  <td>
                    <QosChip meet={s.actual?.qosMeet} />
                  </td>
                  <td className="mono nowrap">
                    {num(s.actual?.avgDelayMs, 1)} / {num(s.actual?.jitterMs, 1)} ms
                  </td>
                  <td className="mono nowrap" title={s.path?.pathId ?? "路径未知"}>
                    {s.path?.pathId ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="empty">当前筛选下没有业务</p>}
      {services.length > rows.length && (
        <p className="muted pad">
          显示 {rows.length} / {services.length} 条（按不达标与优先级排序）
        </p>
      )}
    </section>
  );
}
