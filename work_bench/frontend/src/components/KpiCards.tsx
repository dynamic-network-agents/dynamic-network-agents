/**
 * 首行 5 张 KPI。口径写在 title 里，未知值显示「—」而不是 0。
 *
 * - 在线节点：status === online；状态缺失单独计「未知」
 * - 活动链路：status === up；down / 缺失分开计
 * - 测试业务：分母是「取到分类的业务数」，unknown 不计入分母
 * - 风险链路：来自 riskSummary；unknown=true 时显示「—」
 * - 整体状态：来自 overallStatus（规则 B），并给出触发理由
 */
import type { Snapshot } from "../types";
import { overallTone, OVERALL_LABEL, type Stats, type Tone } from "../lib/derive";
import { DASH } from "../lib/format";

interface Props {
  snap: Snapshot | null;
  stats: Stats;
}

function Kpi(props: {
  label: string;
  value: string;
  sub: string;
  tone?: Tone;
  title?: string;
}) {
  return (
    <div className="kpi" title={props.title}>
      <span className="kpi-label">{props.label}</span>
      <div className={`kpi-value${props.tone ? ` tone-${props.tone}` : ""}`}>{props.value}</div>
      <span className="kpi-sub">{props.sub}</span>
    </div>
  );
}

export default function KpiCards({ snap, stats }: Props) {
  const risk = snap?.riskSummary;
  const ratio = risk?.byCode ?? {};
  const riskValue = !risk || risk.unknown ? DASH : String(risk.total ?? DASH);
  const riskSub = risk?.unknown
    ? (risk.note ?? "数据不可信")
    : `R1 ${ratio.R1 ?? 0} · R3 ${ratio.R3 ?? 0} · R2 ${ratio.R2 ?? 0}`;

  const overall = snap?.overallStatus;
  const overallValue = overall ? (OVERALL_LABEL[overall.status] ?? overall.status) : DASH;
  const overallSub = overall?.reasons?.[0] ?? "无判定依据";

  const catSub =
    stats.catUnknown > 0
      ? `未知分类 ${stats.catUnknown} 条（不计入分母）`
      : `分类来源：${snap?.svc_meta?.ok ? "实时 svc-meta" : snap?.offline ? "离线映射" : "不可用"}`;

  const testRate = stats.test.rate;

  return (
    <section className="kpis" aria-label="总览指标">
      <Kpi
        label="在线节点"
        value={stats.nodeTotal === 0 ? DASH : `${stats.nodeOnline}/${stats.nodeTotal}`}
        sub={stats.nodeUnknown > 0 ? `状态未知 ${stats.nodeUnknown}` : "全部状态已知"}
        title="node.status === online；缺失状态单独计未知"
      />
      <Kpi
        label="活动链路"
        value={stats.linkTotal === 0 ? DASH : `${stats.linkUp}/${stats.linkTotal}`}
        sub={`断开 ${stats.linkDown}${stats.linkUnknown > 0 ? ` · 未知 ${stats.linkUnknown}` : ""}`}
        tone={stats.linkDown > 0 ? "bad" : undefined}
        title="link.status === up；down 表示链路断开（R1）"
      />
      <Kpi
        label="测试业务"
        value={stats.catKnown === 0 ? DASH : `${stats.catTest}/${stats.catKnown}`}
        sub={
          testRate == null
            ? catSub
            : `实测达标 ${(testRate * 100).toFixed(0)}%（${stats.test.meet}/${stats.test.judged}）`
        }
        title={`分母只含 test+background；${catSub}`}
      />
      <Kpi
        label="风险链路"
        value={riskValue}
        sub={riskSub}
        tone={risk && !risk.unknown && (risk.total ?? 0) > 0 ? "warn" : undefined}
        title="R1 断 / R3 相对上一快照劣化 / R2 需求超订（R2 是需求侧估算，不是实测吞吐）"
      />
      <Kpi
        label="整体状态"
        value={overallValue}
        sub={overallSub}
        tone={overallTone(overall?.status)}
        title={overall?.reasons?.join("；") ?? "health 非 live 时不判定"}
      />
    </section>
  );
}
