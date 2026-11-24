/**
 * 数据检查（默认折叠）：采集元信息 + 原始快照 JSON。
 * 原始 JSON 只在展开时渲染，避免 500 条业务时拖慢首屏。
 */
import { useState } from "react";
import type { Snapshot } from "../types";
import { isoClock } from "../lib/format";

interface Props {
  snap: Snapshot;
  lastUpdate: Date | null;
  error: string | null;
}

export default function DataInspector({ snap, lastUpdate, error }: Props) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(snap, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <details
      className="card debug-card"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        数据检查（采集元信息与原始快照）
        <span className="muted"> · v{snap.snapshot_version ?? "?"} · health={snap.health}</span>
      </summary>

      <div className="card-body">
        <div className="dr-grid cols-3">
          <div className="dr">
            <span className="dr-k">快照时间</span>
            <span className="dr-v mono">{snap.received_at}</span>
          </div>
          <div className="dr">
            <span className="dr-k">最近成功采集</span>
            <span className="dr-v mono">{isoClock(snap.last_success_at)}</span>
          </div>
          <div className="dr">
            <span className="dr-k">页面最近更新</span>
            <span className="dr-v mono">{lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}</span>
          </div>
          <div className="dr">
            <span className="dr-k">数据龄</span>
            <span className="dr-v mono">{snap.data_age_s != null ? `${snap.data_age_s.toFixed(3)}s` : "—"}</span>
          </div>
          <div className="dr">
            <span className="dr-k">陈旧资源</span>
            <span className="dr-v mono">{snap.stale_resources?.length ? snap.stale_resources.join(", ") : "—"}</span>
          </div>
          <div className="dr">
            <span className="dr-k">分页</span>
            <span className="dr-v mono">
              links {snap.pagination?.links?.count ?? "—"}（{snap.pagination?.links?.pages ?? "—"} 页，
              {snap.pagination?.links?.complete ? "完整" : "不完整"}）· services{" "}
              {snap.pagination?.services?.count ?? "—"} /topology{" "}
              {snap.pagination?.topology_links ?? "—"} ·{" "}
              {snap.pagination?.consistent === false ? "不一致" : "一致"}
            </span>
          </div>
          <div className="dr">
            <span className="dr-k">svc-meta</span>
            <span className="dr-v mono">
              {snap.svc_meta?.enabled ? (snap.svc_meta.ok ? `ok（${snap.svc_meta.count}）` : "失败") : "关闭"}
              {snap.svc_meta?.error ? ` · ${snap.svc_meta.error}` : ""}
            </span>
          </div>
          <div className="dr">
            <span className="dr-k">事件游标</span>
            <span className="dr-v mono">{snap.events_cursor}</span>
          </div>
          <div className="dr">
            <span className="dr-k">采集错误</span>
            <span className="dr-v mono">{snap.errors.length > 0 ? snap.errors.join(" / ") : "—"}</span>
          </div>
          {error && (
            <div className="dr">
              <span className="dr-k">前端请求错误</span>
              <span className="dr-v mono bad">{error}</span>
            </div>
          )}
        </div>

        {open && (
          <>
            <div className="inspector-actions">
              <button type="button" className="btn btn-ghost" onClick={copy}>
                {copied ? "已复制" : "复制 JSON"}
              </button>
              <span className="muted">原始快照（/api/snapshot 响应体）</span>
            </div>
            <pre className="raw-json">{JSON.stringify(snap, null, 2)}</pre>
          </>
        )}
      </div>
    </details>
  );
}
