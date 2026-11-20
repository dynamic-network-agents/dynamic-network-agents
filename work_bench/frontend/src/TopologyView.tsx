import { useMemo, useRef, useState } from "react";
import type { Link, Node } from "./types";

const NODE_COLORS: Record<string, string> = {
  uav: "#2563eb",
  ground: "#059669",
  air: "#d97706",
};

const LINK_COLORS: Record<string, string> = {
  up: "#94a3b8",
  down: "#ef4444",
};

interface Props {
  nodes: Node[];
  links: Link[];
  highlightLinks?: Set<string>;
}

export default function TopologyView({ nodes, links, highlightLinks }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [viewBox, setViewBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; vx: number; vy: number } | null>(null);

  const positioned = useMemo(() => nodes.filter((n) => n.position), [nodes]);

  // 首次拿到坐标后，按节点包围盒自适应 viewBox
  useMemo(() => {
    if (viewBox || positioned.length === 0) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of positioned) {
      const p = n.position!;
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    }
    const pad = Math.max((maxX - minX) * 0.05, (maxY - minY) * 0.05, 1000);
    setViewBox({ x: minX - pad, y: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 });
  }, [positioned, viewBox]);

  const nodeById = useMemo(() => {
    const m = new Map<string, Node>();
    for (const n of nodes) m.set(n.nodeId, n);
    return m;
  }, [nodes]);

  const onWheel = (e: React.WheelEvent) => {
    if (!viewBox) return;
    const factor = e.deltaY < 0 ? 0.85 : 1.18;
    const cx = viewBox.x + viewBox.w / 2;
    const cy = viewBox.y + viewBox.h / 2;
    const w = viewBox.w * factor;
    const h = viewBox.h * factor;
    setViewBox({ x: cx - w / 2, y: cy - h / 2, w, h });
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (!viewBox) return;
    dragRef.current = { startX: e.clientX, startY: e.clientY, vx: viewBox.x, vy: viewBox.y };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragRef.current || !viewBox) return;
    const scale = viewBox.w / (svgRef.current?.clientWidth || 1);
    const dx = (e.clientX - dragRef.current.startX) * scale;
    const dy = (e.clientY - dragRef.current.startY) * scale;
    setViewBox({ ...viewBox, x: dragRef.current.vx - dx, y: dragRef.current.vy - dy });
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const resetView = () => setViewBox(null);

  return (
    <div className="topo-wrap">
      <div className="topo-toolbar">
        <span>{positioned.length}/{nodes.length} 节点有坐标</span>
        <button onClick={resetView}>复位视图</button>
      </div>
      <svg
        ref={svgRef}
        className="topo-svg"
        viewBox={viewBox ? `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}` : undefined}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        {links.map((l) => {
          const s = nodeById.get(l.srcNodeId);
          const d = nodeById.get(l.dstNodeId);
          if (!s?.position || !d?.position) return null;
          const color = highlightLinks?.has(l.linkId)
            ? "#f59e0b"
            : LINK_COLORS[l.status ?? "up"] ?? "#94a3b8";
          const width = highlightLinks?.has(l.linkId) ? 3 : 1;
          return (
            <line
              key={l.linkId}
              x1={s.position.x}
              y1={s.position.y}
              x2={d.position.x}
              y2={d.position.y}
              stroke={color}
              strokeWidth={width}
              opacity={l.status === "down" ? 0.5 : 0.85}
            >
              <title>{`${l.linkId} ${l.linkType} ${l.status}`}</title>
            </line>
          );
        })}
        {positioned.map((n) => {
          const p = n.position!;
          const color = NODE_COLORS[n.nodeType] ?? "#64748b";
          const offline = n.status === "offline";
          return (
            <g key={n.nodeId}>
              <circle
                cx={p.x}
                cy={p.y}
                r={viewBox ? viewBox.w * 0.006 : 8}
                fill={offline ? "#cbd5e1" : color}
                stroke={offline ? "#94a3b8" : "#0f172a"}
                strokeWidth={1}
              >
                <title>{`${n.nodeId} ${n.name} ${n.nodeType} ${n.status}`}</title>
              </circle>
              <text
                x={p.x}
                y={p.y - (viewBox ? viewBox.w * 0.009 : 12)}
                textAnchor="middle"
                fontSize={viewBox ? viewBox.w * 0.008 : 10}
                fill="#0f172a"
              >
                {n.nodeId}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
