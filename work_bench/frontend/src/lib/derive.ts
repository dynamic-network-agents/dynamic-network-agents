/**
 * 快照 → 派生指标。
 *
 * 口径（与后端 analysis/ 保持一致，前端不另立公式）：
 * - 分类只认后端给的 `category`，`unknown` 不算 test/background；
 * - 达标率分母只算「有实测结论」的业务，未知单独计数；
 * - 需求/容量是**需求侧估算**，不是实测吞吐；
 * - 风险链路 = `snapshot.riskLinks`，`riskSummary.unknown` 时数量显示「—」。
 */
import type { LinkLoad, Snapshot } from "../types";

export type Tone = "ok" | "warn" | "bad" | "idle";

export const HEALTH_LABEL: Record<string, string> = {
  live: "正常",
  partial: "部分接口失败",
  stale: "数据延迟",
  disconnected: "断开",
  offline: "离线",
};

export function healthLabel(health?: string): string {
  if (!health) return "未知";
  return HEALTH_LABEL[health] ?? health;
}

export function healthTone(health?: string): Tone {
  if (health === "live") return "ok";
  if (health === "partial" || health === "stale") return "warn";
  if (health === "offline") return "idle";
  return "bad";
}

export const SIM_LABEL: Record<string, string> = {
  running: "运行中",
  paused: "已暂停",
  joining: "建网中",
  finished: "已结束",
  idle: "空闲",
  unknown: "未知",
};

export function simLabel(status?: string | null): string {
  if (!status) return SIM_LABEL.unknown;
  return SIM_LABEL[status] ?? status;
}

export function simTone(status?: string | null): Tone {
  if (status === "running") return "ok";
  if (status === "paused" || status === "joining") return "warn";
  if (status === "finished" || status === "idle") return "idle";
  return "idle";
}

export const OVERALL_LABEL: Record<string, string> = {
  normal: "正常",
  alarm: "告警",
  critical: "异常",
  unknown: "未知",
};

export function overallTone(status?: string | null): Tone {
  if (status === "normal") return "ok";
  if (status === "alarm") return "warn";
  if (status === "critical") return "bad";
  return "idle";
}

export interface MeetRate {
  judged: number;
  meet: number;
  unknown: number;
  rate: number | null;
}

function meetRate(services: Snapshot["services"]): MeetRate {
  let meet = 0;
  let unknown = 0;
  for (const s of services) {
    const q = s.actual?.qosMeet;
    if (q === true) meet += 1;
    else if (q === false) continue;
    else unknown += 1;
  }
  const judged = services.length - unknown;
  return { judged, meet, unknown, rate: judged > 0 ? meet / judged : null };
}

export interface Stats {
  nodeTotal: number;
  nodeOnline: number;
  nodeUnknown: number;
  linkTotal: number;
  linkUp: number;
  linkDown: number;
  linkUnknown: number;
  catTest: number;
  catBackground: number;
  catKnown: number;
  catUnknown: number;
  all: MeetRate;
  test: MeetRate;
  background: MeetRate;
  flowCount: number;
  runningServices: number;
}

export function computeStats(snap: Snapshot | null): Stats {
  const services = snap?.services ?? [];
  const nodes = snap?.nodes ?? [];
  const links = snap?.links ?? [];
  const test = services.filter((s) => s.category === "test");
  const background = services.filter((s) => s.category === "background");
  return {
    nodeTotal: nodes.length,
    nodeOnline: nodes.filter((n) => n.status === "online").length,
    nodeUnknown: nodes.filter((n) => n.status !== "online" && n.status !== "offline").length,
    linkTotal: links.length,
    linkUp: links.filter((l) => l.status === "up").length,
    linkDown: links.filter((l) => l.status === "down").length,
    linkUnknown: links.filter((l) => l.status !== "up" && l.status !== "down").length,
    catTest: test.length,
    catBackground: background.length,
    catKnown: test.length + background.length,
    catUnknown: services.length - test.length - background.length,
    all: meetRate(services),
    test: meetRate(test),
    background: meetRate(background),
    flowCount: snap?.flows?.length ?? 0,
    runningServices: services.filter((s) => s.status === "running").length,
  };
}

/** 需求侧负载排行：利用率降序，无利用率（容量缺失）排最后。 */
export function hotspotLinks(loads: LinkLoad[], limit = 5): LinkLoad[] {
  const withUtil = loads.filter((l) => l.demandUtilization !== null);
  const withoutUtil = loads.filter((l) => l.demandUtilization === null);
  withUtil.sort((a, b) => (b.demandUtilization ?? 0) - (a.demandUtilization ?? 0));
  withoutUtil.sort((a, b) => b.demandBps - a.demandBps);
  return [...withUtil, ...withoutUtil].slice(0, limit);
}

/** 业务表格排序：不达标优先，其次未知，再达标；同组按优先级降序、ID 升序。 */
export function serviceSeverity(qosMeet?: boolean | null): number {
  if (qosMeet === false) return 0;
  if (qosMeet === null || qosMeet === undefined) return 1;
  return 2;
}

export function sortServicesForTriage<T extends { serviceId: string; priority?: number; actual?: { qosMeet?: boolean } | null }>(
  services: T[]
): T[] {
  return [...services].sort((a, b) => {
    const sa = serviceSeverity(a.actual?.qosMeet);
    const sb = serviceSeverity(b.actual?.qosMeet);
    if (sa !== sb) return sa - sb;
    const pa = a.priority ?? 0;
    const pb = b.priority ?? 0;
    if (pa !== pb) return pb - pa;
    return a.serviceId < b.serviceId ? -1 : 1;
  });
}
