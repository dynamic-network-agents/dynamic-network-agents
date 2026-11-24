/**
 * 拓扑面板：图例 + 过滤（节点类型 / 只看风险）+ 画布。
 *
 * 过滤只影响绘制，不改变数据；「只看风险」会同时收窄端点节点，避免留下孤立点。
 */
import { useMemo, useState } from "react";
import type { Link, LinkRisk, Node } from "../types";
import TopologyView from "../TopologyView";

const NODE_TYPE_LABEL: Record<string, string> = {
  uav: "UAV",
  ground: "地面",
  air: "空中",
  ext: "外部引接",
};

interface Props {
  nodes: Node[];
  links: Link[];
  risks: LinkRisk[];
  highlightLinks: Set<string>;
  selectedNodeId: string | null;
  selectedLinkId: string | null;
  onSelectNode: (nodeId: string) => void;
  onSelectLink: (linkId: string) => void;
  onClearSelection: () => void;
}

export default function TopologyPanel({
  nodes,
  links,
  risks,
  highlightLinks,
  selectedNodeId,
  selectedLinkId,
  onSelectNode,
  onSelectLink,
  onClearSelection,
}: Props) {
  const types = useMemo(() => {
    const set = new Set<string>();
    for (const n of nodes) set.add(n.nodeType ?? "unknown");
    return Array.from(set).sort();
  }, [nodes]);

  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [onlyRisk, setOnlyRisk] = useState(false);

  const riskIds = useMemo(() => new Set(risks.map((r) => r.linkId)), [risks]);

  const { viewNodes, viewLinks } = useMemo(() => {
    let ns = nodes.filter((n) => !hidden.has(n.nodeType ?? "unknown"));
    let ls = links;
    if (onlyRisk) {
      ls = links.filter((l) => riskIds.has(l.linkId));
      const keep = new Set(ls.flatMap((l) => [l.srcNodeId, l.dstNodeId]));
      ns = ns.filter((n) => keep.has(n.nodeId));
    }
    return { viewNodes: ns, viewLinks: ls };
  }, [nodes, links, hidden, onlyRisk, riskIds]);

  const missingPos = viewNodes.filter((n) => !n.position).length;

  const toggleType = (t: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  return (
    <section className="card topo-card" aria-label="网络拓扑">
      <div className="card-head">
        <div className="card-title">
          <h2>网络拓扑</h2>
          <span className="muted">
            {viewNodes.length} 节点 · {viewLinks.length} 链路
            {missingPos > 0 && ` · ${missingPos} 节点缺坐标未绘制（布局估算）`}
          </span>
        </div>
        <div className="topo-toggles">
          <label className="check">
            <input
              type="checkbox"
              checked={onlyRisk}
              onChange={(e) => setOnlyRisk(e.target.checked)}
            />
            只看风险链路（{riskIds.size}）
          </label>
          <button type="button" className="btn btn-ghost" onClick={onClearSelection}>
            清除选中
          </button>
        </div>
      </div>

      <div className="card-body topo-body">
        <div className="legend" aria-label="图例">
          {types.map((t) => (
            <button
              key={t}
              type="button"
              className={`legend-item${hidden.has(t) ? " is-off" : ""}`}
              onClick={() => toggleType(t)}
              title={`点击${hidden.has(t) ? "显示" : "隐藏"}该类型`}
            >
              <span className={`mark mark-${t}`} aria-hidden="true" />
              {NODE_TYPE_LABEL[t] ?? t}
            </button>
          ))}
          <span className="legend-sep" aria-hidden="true" />
          <span className="legend-item static">
            <span className="line line-normal" aria-hidden="true" />
            正常
          </span>
          <span className="legend-item static">
            <span className="line line-down" aria-hidden="true" />
            断开
          </span>
          <span className="legend-item static">
            <span className="line line-risk" aria-hidden="true" />
            风险（劣化/超订）
          </span>
          <span className="legend-item static">
            <span className="line line-path" aria-hidden="true" />
            选中路径
          </span>
        </div>

        {viewNodes.length === 0 ? (
          <p className="empty">无节点数据（仿真未启动或拓扑采集失败）</p>
        ) : (
          <TopologyView
            nodes={viewNodes}
            links={viewLinks}
            riskLinks={riskIds}
            highlightLinks={highlightLinks}
            selectedNodeId={selectedNodeId}
            selectedLinkId={selectedLinkId}
            onSelectNode={onSelectNode}
            onSelectLink={onSelectLink}
            onClearSelection={onClearSelection}
          />
        )}
      </div>
    </section>
  );
}
