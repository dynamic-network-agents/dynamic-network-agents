/**
 * 右侧诊断栏：实测达标率（按分类）+ 需求侧热点链路 + 风险链路。
 *
 * 口径边界：
 * - 达标率分母只算「有 qosMeet 结论」的业务，unknown 单列；
 * - 分类不可信（svc-meta 不可用且非离线映射）时，test/background 分项标注「分类不可信」；
 * - 热点是 `demandBps / capacityBps` 的**需求侧估算**，不是链路实测吞吐。
 */
import type { LinkLoad, LinkRisk } from "../types";
import { hotspotLinks, type Stats } from "../lib/derive";
import { DASH, mbps, pct } from "../lib/format";

interface Props {
  stats: Stats;
  risks: LinkRisk[];
  loads: LinkLoad[];
  categoryTrusted: boolean;
  onSelectLink: (linkId: string) => void;
}

function RateBar(props: {
  label: string;
  rate: number | null;
  meet: number;
  judged: number;
  unknown: number;
  note?: string;
}) {
  const pctValue = props.rate == null ? 0 : Math.round(props.rate * 100);
  const tone = props.rate == null ? "idle" : props.rate >= 0.9 ? "ok" : props.rate >= 0.7 ? "warn" : "bad";
  return (
    <div className="rate-row" title={props.note}>
      <span className="rate-label">{props.label}</span>
      <span className="bar" aria-hidden="true">
        <span className={`bar-fill tone-${tone}`} style={{ width: `${pctValue}%` }} />
      </span>
      <span className="rate-value">
        {props.rate == null ? DASH : `${pctValue}%`}
        <em>
          {props.meet}/{props.judged}
          {props.unknown > 0 ? ` · 未知 ${props.unknown}` : ""}
        </em>
      </span>
    </div>
  );
}

export default function DiagnosticsPanel({
  stats,
  risks,
  loads,
  categoryTrusted,
  onSelectLink,
}: Props) {
  const hotspots = hotspotLinks(loads, 5);
  const shownRisks = risks.slice(0, 6);

  return (
    <section className="card diag-card" aria-label="诊断">
      <div className="card-head">
        <div className="card-title">
          <h2>诊断</h2>
          <span className="muted">先看不达标与风险，再下钻</span>
        </div>
      </div>

      <div className="card-body diag-body">
        <div className="diag-block">
          <h3>实测 QoS 达标率</h3>
          <RateBar
            label="全部业务"
            rate={stats.all.rate}
            meet={stats.all.meet}
            judged={stats.all.judged}
            unknown={stats.all.unknown}
            note="分母 = 有 qosMeet 结论的业务；qosMeet 是仿真器给出的综合判定"
          />
          <RateBar
            label="测试业务"
            rate={categoryTrusted ? stats.test.rate : null}
            meet={stats.test.meet}
            judged={stats.test.judged}
            unknown={stats.test.unknown}
            note={categoryTrusted ? "分类来自 svc-meta / 离线映射" : "分类不可信：svc-meta 不可用"}
          />
          <RateBar
            label="背景业务"
            rate={categoryTrusted ? stats.background.rate : null}
            meet={stats.background.meet}
            judged={stats.background.judged}
            unknown={stats.background.unknown}
            note={categoryTrusted ? "分类来自 svc-meta / 离线映射" : "分类不可信：svc-meta 不可用"}
          />
          <p className="muted">
            {categoryTrusted
              ? `分类来源：${stats.catKnown} 条已识别，${stats.catUnknown} 条未知（未知不计入分母）`
              : "分类不可信：仅显示全部业务的达标率"}
          </p>
        </div>

        <div className="diag-block">
          <h3>
            热点链路 · 需求侧 <span className="tag">估算</span>
          </h3>
          {hotspots.length === 0 ? (
            <p className="empty">无路径数据（业务未运行或路径未知）</p>
          ) : (
            <ul className="rank-list">
              {hotspots.map((l) => {
                const util = l.demandUtilization ?? null;
                const over = util !== null && util > 1;
                return (
                  <li key={l.linkId}>
                    <button type="button" className="rank-row" onClick={() => onSelectLink(l.linkId)}>
                      <span className="rank-id">{l.linkId}</span>
                      <span className="bar" aria-hidden="true">
                        <span
                          className={`bar-fill tone-${over ? "bad" : "ok"}`}
                          style={{ width: `${Math.min((util ?? 0) * 100, 100)}%` }}
                        />
                      </span>
                      <span className={over ? "rank-val bad" : "rank-val"}>{pct(util)}</span>
                      <span className="rank-meta">
                        {mbps(l.demandBps)} / {mbps(l.capacityBps)} Mbps
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="muted">需求/容量，不是链路实测吞吐；超过 100% 表示需求侧超订。</p>
        </div>

        <div className="diag-block">
          <h3>风险链路（{risks.length}）</h3>
          {risks.length === 0 ? (
            <p className="empty">当前无风险链路</p>
          ) : (
            <ul className="risk-list">
              {shownRisks.map((r) => (
                <li key={r.linkId}>
                  <button type="button" className="risk-row" onClick={() => onSelectLink(r.linkId)}>
                    <span className={`sev sev-${r.severity}`}>{r.severity}</span>
                    <span className="risk-body">
                      <b>
                        {r.linkId} <small>{r.codes.join(" ")}</small>
                      </b>
                      <span>{r.reasons[0]}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {risks.length > shownRisks.length && (
            <p className="muted">另有 {risks.length - shownRisks.length} 条，见「链路负载」表。</p>
          )}
          <p className="muted">R1 断开 · R3 相对上一快照劣化 · R2 需求超订（估算）</p>
        </div>
      </div>
    </section>
  );
}
