/**
 * 顶部状态栏：仿真实例 / 运行状态 / 仿真时间 / 数据健康 / 最近更新。
 *
 * 口径：
 * - 运行态来自控制面 run-info（`sim`）；取不到时显示「未知」并给出原因，不猜；
 * - 「已运行」= `/time` 的 tsUs − run-info 的 t0TsUs（两者都有才算）；
 * - 数据龄 `data_age_s` 是**本地采集**新鲜度，不是上游缓存延迟。
 */
import { useMemo } from "react";
import type { Snapshot } from "../types";
import {
  clockFromUs,
  elapsedFromUs,
  isoClock,
  DASH,
} from "../lib/format";
import { healthLabel, healthTone, simLabel, simTone } from "../lib/derive";

interface Props {
  snap: Snapshot | null;
  error: string | null;
  lastUpdate: Date | null;
}

export default function TopBar({ snap, error, lastUpdate }: Props) {
  const sim = snap?.sim;
  const elapsed = useMemo(() => {
    const now = snap?.sim_time_us;
    const t0 = sim?.t0TsUs;
    if (now == null || t0 == null || now < t0) return null;
    return now - t0;
  }, [snap?.sim_time_us, sim?.t0TsUs]);

  const progress =
    sim?.engineTotal != null && sim.engineTotal > 0
      ? `${sim.engineFired ?? 0}/${sim.engineTotal}`
      : null;

  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className={`chip tone-${simTone(sim?.status)}`} title={sim?.error ?? undefined}>
          <span className="chip-dot" aria-hidden="true" />
          {simLabel(sim?.status)}
        </span>
        <span className="kv" title="当前仿真实例">
          <i>实例</i>
          {snap?.instance_id ?? DASH}
        </span>
        <span className="kv" title="场景">
          <i>场景</i>
          {sim?.scenarioId ?? snap?.scenario_id ?? DASH}
        </span>
        <span className="kv" title="脚本与推进进度（run-info）">
          <i>脚本</i>
          {sim?.scriptId ?? DASH}
          {progress && <em>{progress}</em>}
        </span>
      </div>

      <div className="topbar-right">
        <span className="kv" title="已运行 = 当前 tsUs − t0TsUs">
          <i>已运行</i>
          {elapsed != null ? elapsedFromUs(elapsed) : DASH}
        </span>
        <span className="kv" title="当前仿真时间（/time 的 tsUs）">
          <i>仿真时刻</i>
          {clockFromUs(snap?.sim_time_us)}
        </span>
        <span className={`chip tone-${healthTone(snap?.health)}`} title={`health=${snap?.health ?? "unknown"}`}>
          <span className="chip-dot" aria-hidden="true" />
          {healthLabel(snap?.health)}
        </span>
        {snap?.data_age_s != null && (
          <span className="kv" title="本地最近一次成功采集距今；超过 3× 轮询即视为延迟">
            <i>数据龄</i>
            {snap.data_age_s.toFixed(1)}s
          </span>
        )}
        {snap?.offline && <span className="chip tone-idle">离线场景</span>}
        <span className="kv" title="前端最近一次拿到快照的本地时间">
          <i>更新</i>
          {lastUpdate ? lastUpdate.toLocaleTimeString() : DASH}
        </span>
        {error && (
          <span className="chip tone-bad" title={error}>
            请求失败
          </span>
        )}
      </div>

      {snap && (snap.errors.length > 0 || snap.pagination?.note || snap.sim?.error) && (
        <div className="topbar-strip" role="status">
          {snap.sim?.error && sim?.status === "unknown" && (
            <span>运行态不可用：{snap.sim.error}</span>
          )}
          {snap.errors.length > 0 && <span>部分接口失败：{snap.errors.join(" / ")}</span>}
          {snap.pagination?.note && <span>分页：{snap.pagination.note}</span>}
          {snap.last_success_at && <span>最近成功采集：{isoClock(snap.last_success_at)}</span>}
        </div>
      )}
    </header>
  );
}
