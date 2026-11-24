/**
 * 展示层格式化。
 *
 * 统一口径：缺失值一律显示「—」，**不把缺失显示成 0**（工作台数据诚实约束）。
 */

export const DASH = "—";

export function num(v?: number | null, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return Number(v).toFixed(digits);
}

/** bps → Mbps（链路容量与需求带宽统一用 Mbps 展示）。 */
export function mbps(bps?: number | null, digits = 1): string {
  if (bps === null || bps === undefined) return DASH;
  return (bps / 1e6).toFixed(digits);
}

/** 利用率（0~1）→ 百分比；>100% 表示需求侧超订（估算）。 */
export function pct(u?: number | null, digits = 0): string {
  if (u === null || u === undefined) return DASH;
  return `${(u * 100).toFixed(digits)}%`;
}

/** 仿真时间戳（µs，epoch）→ 本地时钟。 */
export function clockFromUs(us?: number | null): string {
  if (us === null || us === undefined || us <= 0) return DASH;
  const d = new Date(Math.floor(us / 1000));
  return Number.isNaN(d.getTime()) ? DASH : d.toLocaleTimeString();
}

/** 时长（µs）→ 1h 02m 03s；用于「已运行」。 */
export function elapsedFromUs(us?: number | null): string {
  if (us === null || us === undefined || us < 0) return DASH;
  const total = Math.floor(us / 1e6);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}h ${mm}m ${ss}s` : `${m}m ${ss}s`;
}

export function isoClock(iso?: string | null): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : d.toLocaleTimeString();
}

/** 路径 segments → "L1 → L2"；只看 link 元素。 */
export function segIds(segments?: { type: string; id: string }[] | null): string {
  if (!segments || segments.length === 0) return DASH;
  const ids = segments.filter((s) => s.type === "link").map((s) => s.id);
  return ids.length > 0 ? ids.join(" → ") : DASH;
}

export function truncateList(items: string[], keep = 3): string {
  if (items.length === 0) return DASH;
  if (items.length <= keep) return items.join(", ");
  return `${items.slice(0, keep).join(", ")}…`;
}
