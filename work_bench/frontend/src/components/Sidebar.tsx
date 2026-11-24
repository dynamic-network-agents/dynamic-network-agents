/**
 * 左侧主导航。首版开放「全局总览」与「业务分析（Flow 视图）」，
 * 其余入口保留位置并明确标注未开放——不做假入口。
 */

export type PageKey = "overview" | "flows";

const NAV: { key: string; label: string; page?: PageKey; ready: boolean }[] = [
  { key: "overview", label: "全局总览", page: "overview", ready: true },
  { key: "network", label: "网络分析", ready: false },
  { key: "service", label: "业务分析", page: "flows", ready: true },
  { key: "qos", label: "QoS 诊断", ready: false },
  { key: "path", label: "路径对比", ready: false },
  { key: "event", label: "事件时间轴", ready: false },
  { key: "replay", label: "历史回放", ready: false },
  { key: "settings", label: "系统设置", ready: false },
];

interface Props {
  page: PageKey;
  onNavigate: (page: PageKey) => void;
}

export default function Sidebar({ page, onNavigate }: Props) {
  return (
    <aside className="sidebar" aria-label="主导航">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span className="brand-text">
          <b>B03 Work Bench</b>
          <small>网络观测与诊断</small>
        </span>
      </div>

      <nav className="nav">
        {NAV.map((item) => {
          const active = item.page === page;
          return (
            <button
              key={item.key}
              type="button"
              className={`nav-item${active ? " is-active" : ""}`}
              disabled={!item.ready}
              aria-current={active ? "page" : undefined}
              title={item.ready ? item.label : `${item.label}：后续版本开放`}
              onClick={() => item.page && onNavigate(item.page)}
            >
              <span className="nav-dot" aria-hidden="true" />
              {item.label}
              {!item.ready && <span className="nav-soon">未开放</span>}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        <p>只读观测。唯一写接口是改业务路径，默认关闭在页面底部提示。</p>
        <p className="muted">观测通道：ctrl 令牌（不计入 agent 统计）</p>
      </div>
    </aside>
  );
}
