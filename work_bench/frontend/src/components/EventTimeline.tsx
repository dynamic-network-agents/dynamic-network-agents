/**
 * 事件时间轴摘要：只展示 `/events` 的**实际事件**（不含脚本计划事件）。
 * 计划事件若后续接入，必须与本列表分轨并单独标注。
 */
import type { SimEvent } from "../types";
import { clockFromUs } from "../lib/format";

interface Props {
  events: SimEvent[];
}

const LIMIT = 6;

function payloadValue(payload: Record<string, unknown> | undefined, key: string): string | null {
  const v = payload?.[key];
  return typeof v === "string" || typeof v === "number" ? String(v) : null;
}

function summary(e: SimEvent): string {
  const p = e.payload;
  const parts: string[] = [];
  for (const key of ["serviceId", "linkId", "nodeId", "instanceId"]) {
    const v = payloadValue(p, key);
    if (v) parts.push(v);
  }
  const status = payloadValue(p, "status");
  if (status) parts.push(`→ ${status}`);
  const reason = payloadValue(p, "reason") ?? payloadValue(p, "reasonText");
  if (reason) parts.push(reason);
  return parts.length > 0 ? parts.join(" · ") : "—";
}

export default function EventTimeline({ events }: Props) {
  const rows = [...events].slice(-LIMIT).reverse();

  return (
    <section className="card" aria-label="最近事件">
      <div className="card-head">
        <div className="card-title">
          <h2>最近事件</h2>
          <span className="muted">实际事件 /events · 共 {events.length} 条</span>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="empty pad">暂无事件（仿真未产生状态变化，或事件接口不可用）</p>
      ) : (
        <ol className="timeline">
          {rows.map((e) => (
            <li key={e.eventId}>
              <span className="tl-time mono">{clockFromUs(e.tsUs) !== "—" ? clockFromUs(e.tsUs) : (e.time ?? "—")}</span>
              <span className="tl-content">
                <b>{e.type}</b>
                <span className="mono">{summary(e)}</span>
              </span>
              <span
                className="tl-json mono"
                title={JSON.stringify(e.payload ?? {}, null, 2)}
              >
                payload
              </span>
            </li>
          ))}
        </ol>
      )}
      <p className="muted pad">事件的 payload 以 tooltip 展示；时间优先取 tsUs，缺失时回退 time 字段。</p>
    </section>
  );
}
