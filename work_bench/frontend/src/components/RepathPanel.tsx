/**
 * 调试写操作：改业务路径（全项目唯一写接口，经后端 /api/repath 受开关控制）。
 *
 * 必须明确提示：路径是 flow 级，改一条会同时改变同源目的的全部业务。
 * 正式录分时应由 `WORKBENCH_ALLOW_REPATH=0` 关闭，此时后端返回 403。
 */
import { useEffect, useState } from "react";
import { fetchCandidates, postRepath, type RepathResult } from "../api";
import type { CandidatePath, Service } from "../types";

interface Props {
  services: Service[];
}

export default function RepathPanel({ services }: Props) {
  const [serviceId, setServiceId] = useState("");
  const [candidates, setCandidates] = useState<CandidatePath[]>([]);
  const [pathIdx, setPathIdx] = useState<number>(-1);
  const [manual, setManual] = useState("");
  const [result, setResult] = useState<RepathResult | null>(null);
  const [busy, setBusy] = useState(false);

  const svc = services.find((s) => s.serviceId === serviceId);

  useEffect(() => {
    setCandidates([]);
    setPathIdx(-1);
    setResult(null);
    if (!serviceId) return;
    fetchCandidates(serviceId)
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, [serviceId]);

  const submit = async () => {
    if (!svc?.srcNodeId || !svc?.dstNodeId) return;
    let segments: { type: string; id: string }[] = [];
    if (pathIdx >= 0 && candidates[pathIdx]) {
      segments = candidates[pathIdx].links.map((id) => ({ type: "link", id }));
    } else if (manual.trim()) {
      segments = manual
        .split(/[,，\s]+/)
        .filter(Boolean)
        .map((id) => ({ type: "link", id }));
    }
    if (segments.length === 0) {
      setResult({ ok: false, msg: "未选择或填写路径" });
      return;
    }
    const ok = window.confirm(
      `确认把业务 ${serviceId} 改到路径 [${segments.map((s) => s.id).join(" → ")}]？\n\n` +
        `注意：路径是 flow 级，改这一条会同时改变同源目的（${svc.srcNodeId}→${svc.dstNodeId}）的其他业务。`
    );
    if (!ok) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await postRepath({
        serviceId,
        srcNodeId: svc.srcNodeId,
        dstNodeId: svc.dstNodeId,
        segments,
      });
      setResult(r);
    } catch (e) {
      setResult({ ok: false, msg: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="repath">
      <div className="repath-row">
        <label className="field">
          <span>业务</span>
          <select value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
            <option value="">选择业务…</option>
            {services.map((s) => (
              <option key={s.serviceId} value={s.serviceId}>
                {s.serviceId}（{s.category ?? "unknown"}）{s.srcNodeId ?? "?"}→{s.dstNodeId ?? "?"}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>候选路径</span>
          <select
            value={pathIdx}
            onChange={(e) => setPathIdx(Number(e.target.value))}
            disabled={!svc || candidates.length === 0}
          >
            <option value={-1}>
              {svc && candidates.length === 0 ? "无候选数据（service-paths.json）" : "自动（候选列表）"}
            </option>
            {candidates.map((c, i) => (
              <option key={i} value={i}>
                路径{c.pathNo}：[{c.links.join(" → ")}]
              </option>
            ))}
          </select>
        </label>

        <label className="field grow">
          <span>或手动填 linkId</span>
          <input
            placeholder="逗号分隔，如 L00001,L00002"
            value={manual}
            onChange={(e) => setManual(e.target.value)}
          />
        </label>

        <button type="button" className="btn btn-warn" onClick={submit} disabled={busy || !serviceId}>
          {busy ? "提交中…" : "提交更改"}
        </button>
      </div>

      <p className="muted">
        改一条业务 = 改整条 flow（同源目的全部业务受影响）。这是唯一写接口；正式录分请置
        <code> WORKBENCH_ALLOW_REPATH=0</code>，届时后端返回 403。
      </p>

      {result && (
        <pre className={`result${result.ok ? " is-ok" : " is-bad"}`}>
          {result.ok ? "✓ accepted" : `✗ ${result.code ?? ""} ${result.msg ?? ""}`}
          {"\n"}
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      {result?.warning && <p className="warn">⚠ {result.warning}</p>}
    </div>
  );
}
