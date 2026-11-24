import type { CandidatePath, Snapshot } from "./types";

export async function fetchSnapshot(): Promise<Snapshot> {
  const resp = await fetch("/api/snapshot");
  if (!resp.ok) {
    throw new Error(`snapshot HTTP ${resp.status}`);
  }
  return (await resp.json()) as Snapshot;
}

export async function fetchCandidates(serviceId: string): Promise<CandidatePath[]> {
  const resp = await fetch(`/api/candidates?serviceId=${encodeURIComponent(serviceId)}`);
  if (resp.status === 404) {
    return [];
  }
  if (!resp.ok) {
    throw new Error(`candidates HTTP ${resp.status}`);
  }
  const data = (await resp.json()) as { paths: CandidatePath[] };
  return data.paths ?? [];
}

export interface RepathResult {
  ok: boolean;
  code?: number;
  msg?: string;
  result?: string;
  pathId?: string;
  effectiveTime?: string;
  effectiveTsUs?: number;
  envelope?: unknown;
  warning?: string;
}

export async function postRepath(body: {
  serviceId: string;
  srcNodeId: string;
  dstNodeId: string;
  segments: { type: string; id: string }[];
}): Promise<RepathResult> {
  const resp = await fetch("/api/repath", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    // 403（写开关关闭）等：后端 detail 里有可读原因
    let detail = "";
    try {
      const body = (await resp.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* 非 JSON 响应，保留状态码即可 */
    }
    return {
      ok: false,
      code: resp.status,
      msg: detail || `repath HTTP ${resp.status}`,
    };
  }
  return (await resp.json()) as RepathResult;
}
