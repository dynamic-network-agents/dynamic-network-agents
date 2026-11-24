/**
 * 2D 拓扑（SVG，真实坐标优先）。
 *
 * 视觉编码（不只靠颜色）：
 * - 节点形状区分类型：UAV 圆 / 地面 方 / 空中 三角 / 外部引接 菱形；
 * - 链路：正常实线、断开红色实线、风险红色虚线、选中路径蓝色加粗、当前选中链路琥珀色；
 * - 标签只在节点数较少或放大后出现，避免 300 节点时糊成一片。
 *
 * 坐标缺失的节点不绘制，由外层面板标注「布局估算」。
 */
import { useCallback, useMemo, useRef, useState } from "react";
import type { Link, Node } from "./types";

const NODE_FILL: Record<string, string> = {
  uav: "#2563eb",
  ground: "#0f7a5a",
  air: "#c2760b",
  ext: "#64748b",
};

const LINK_COLOR = { normal: "#94a3b8", down: "#b3261e", risk: "#b3261e", path: "#1d4ed8", selected: "#f59e0b" };

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Props {
  nodes: Node[];
  links: Link[];
  riskLinks: Set<string>;
  highlightLinks?: Set<string>;
  selectedNodeId?: string | null;
  selectedLinkId?: string | null;
  onSelectNode?: (nodeId: string) => void;
  onSelectLink?: (linkId: string) => void;
  onClearSelection?: () => void;
}

function computeBox(nodes: Node[]): Box | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const n of nodes) {
    const p = n.position;
    if (!p) continue;
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  if (!Number.isFinite(minX)) return null;
  const pad = Math.max((maxX - minX) * 0.06, (maxY - minY) * 0.06, 800);
  return {
    x: minX - pad,
    y: minY - pad,
    w: Math.max(maxX - minX + pad * 2, 1),
    h: Math.max(maxY - minY + pad * 2, 1),
  };
}

export default function TopologyView({
  nodes,
  links,
  riskLinks,
  highlightLinks,
  selectedNodeId,
  selectedLinkId,
  onSelectNode,
  onSelectLink,
  onClearSelection,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const movedRef = useRef(false);
  const [box, setBox] = useState<Box | null>(null);

  const positioned = useMemo(() => nodes.filter((n) => n.position), [nodes]);
  const autoBox = useMemo(() => computeBox(positioned), [positioned]);
  const view = box ?? autoBox;

  const nodeById = useMemo(() => {
    const m = new Map<string, Node>();
    for (const n of nodes) m.set(n.nodeId, n);
    return m;
  }, [nodes]);

  const drawableLinks = useMemo(
    () =>
      links.filter((l) => {
        const s = nodeById.get(l.srcNodeId);
        const d = nodeById.get(l.dstNodeId);
        return Boolean(s?.position && d?.position);
      }),
    [links, nodeById]
  );

  const showLabels = positioned.length <= 80 || (view ? view.w < (autoBox?.w ?? 1) * 0.4 : false);

  const onWheel = useCallback(
    (e: React.WheelEvent) => {
      if (!view) return;
      const factor = e.deltaY < 0 ? 0.85 : 1.18;
      const cx = view.x + view.w / 2;
      const cy = view.y + view.h / 2;
      const w = Math.max(view.w * factor, 100);
      const h = Math.max(view.h * factor, 100);
      setBox({ x: cx - w / 2, y: cy - h / 2, w, h });
    },
    [view]
  );

  const onPointerDown = (e: React.PointerEvent) => {
    if (!view) return;
    movedRef.current = false;
    dragRef.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag || !view) return;
    const dxPx = e.clientX - drag.x;
    const dyPx = e.clientY - drag.y;
    if (Math.abs(dxPx) + Math.abs(dyPx) > 4) movedRef.current = true;
    const scale = view.w / (svgRef.current?.clientWidth || 1);
    setBox({ ...view, x: drag.vx - dxPx * scale, y: drag.vy - dyPx * scale });
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const guard = (fn?: () => void) => () => {
    if (movedRef.current) return; // 拖动结束不算点击
    fn?.();
  };

  const r = view ? Math.max(view.w * 0.006, 2.2) : 7;
  const stroke = view ? Math.max(view.w * 0.0009, 0.6) : 1;
  const fontSize = view ? Math.max(view.w * 0.009, 6) : 10;

  return (
    <div className="topo-canvas">
      <svg
        ref={svgRef}
        className="topo-svg"
        viewBox={view ? `${view.x} ${view.y} ${view.w} ${view.h}` : undefined}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClearSelection?.();
        }}
        role="img"
        aria-label={`网络拓扑：${positioned.length} 个节点，${drawableLinks.length} 条链路`}
      >
        {drawableLinks.map((l) => {
          const s = nodeById.get(l.srcNodeId)!.position!;
          const d = nodeById.get(l.dstNodeId)!.position!;
          const isSelected = selectedLinkId === l.linkId;
          const isRisk = riskLinks.has(l.linkId);
          const isDown = l.status === "down";
          const isPath = highlightLinks?.has(l.linkId) ?? false;

          let color = LINK_COLOR.normal;
          let width = stroke;
          let dash: string | undefined;
          if (isPath) {
            color = LINK_COLOR.path;
            width = stroke * 2.6;
          }
          if (isRisk || isDown) {
            color = LINK_COLOR.risk;
            width = stroke * 2;
            dash = isDown ? undefined : "7 5";
          }
          if (isSelected) {
            color = LINK_COLOR.selected;
            width = stroke * 3.4;
            dash = undefined;
          }

          return (
            <line
              key={l.linkId}
              x1={s.x}
              y1={s.y}
              x2={d.x}
              y2={d.y}
              stroke={color}
              strokeWidth={width}
              strokeDasharray={dash}
              opacity={isDown ? 0.75 : 0.9}
              className="topo-link"
              onClick={guard(() => onSelectLink?.(l.linkId))}
            >
              <title>
                {`${l.linkId} · ${l.linkType ?? "—"} · ${l.status ?? "状态未知"}`}
                {isRisk ? " · 风险链路" : ""}
              </title>
            </line>
          );
        })}

        {positioned.map((n) => {
          const p = n.position!;
          const fill = n.status === "offline" ? "#cbd5e1" : NODE_FILL[n.nodeType ?? ""] ?? "#64748b";
          const isSelected = selectedNodeId === n.nodeId;
          const selectedStroke = isSelected ? "#f59e0b" : n.status === "offline" ? "#94a3b8" : "#0f172a";
          const strokeW = isSelected ? stroke * 3 : stroke;
          return (
            <g
              key={n.nodeId}
              className="topo-node"
              onClick={guard(() => onSelectNode?.(n.nodeId))}
            >
              {(n.nodeType ?? "uav") === "ground" ? (
                <rect
                  x={p.x - r}
                  y={p.y - r}
                  width={r * 2}
                  height={r * 2}
                  rx={r * 0.25}
                  fill={fill}
                  stroke={selectedStroke}
                  strokeWidth={strokeW}
                />
              ) : (n.nodeType ?? "uav") === "air" ? (
                <polygon
                  points={`${p.x},${p.y - r * 1.25} ${p.x + r * 1.1},${p.y + r * 0.85} ${p.x - r * 1.1},${p.y + r * 0.85}`}
                  fill={fill}
                  stroke={selectedStroke}
                  strokeWidth={strokeW}
                />
              ) : (n.nodeType ?? "uav") === "ext" ? (
                <polygon
                  points={`${p.x},${p.y - r * 1.2} ${p.x + r * 1.2},${p.y} ${p.x},${p.y + r * 1.2} ${p.x - r * 1.2},${p.y}`}
                  fill={fill}
                  stroke={selectedStroke}
                  strokeWidth={strokeW}
                />
              ) : (
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={r}
                  fill={fill}
                  stroke={selectedStroke}
                  strokeWidth={strokeW}
                />
              )}
              <title>
                {`${n.nodeId} ${n.name ?? ""} · ${n.nodeType ?? "未知类型"} · ${n.status ?? "状态未知"}`}
              </title>
              {showLabels && (
                <text
                  x={p.x}
                  y={p.y - r * 1.6}
                  textAnchor="middle"
                  fontSize={fontSize}
                  fill="#334155"
                  pointerEvents="none"
                >
                  {n.nodeId}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className="topo-actions">
        <button type="button" className="btn btn-ghost" onClick={() => setBox(null)}>
          复位视图
        </button>
        <span className="muted">{positioned.length}/{nodes.length} 有坐标</span>
      </div>
    </div>
  );
}
