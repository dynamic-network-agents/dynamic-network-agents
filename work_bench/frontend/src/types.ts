// 与后端 /api/snapshot 对齐的字段类型

export interface Position {
  x: number;
  y: number;
}

export interface Node {
  nodeId: string;
  name: string;
  nodeType: string;
  ip?: string;
  mask?: string;
  position?: Position;
  status?: string;
}

export interface LinkParams {
  delayMs?: number;
  jitterMs?: number;
  bandwidthBps?: number;
  ber?: number;
  packetLossRate?: number;
}

export interface Link {
  linkId: string;
  linkType: string;
  srcNodeId: string;
  dstNodeId: string;
  status?: string;
  params?: LinkParams;
}

export interface Requirement {
  delayMs?: number;
  jitterMs?: number;
  bandwidthBps?: number;
  ber?: number;
  packetLossRate?: number;
}

export interface PathSegment {
  type: string;
  id: string;
}

export interface ServicePath {
  pathId?: string;
  segments?: PathSegment[];
}

export interface Actual {
  avgDelayMs?: number;
  jitterMs?: number;
  effBwBps?: number;
  errPct?: number;
  packetLossRate?: number;
  qosMeet?: boolean;
}

export interface Service {
  serviceId: string;
  serviceType?: string;
  srcNodeId?: string;
  dstNodeId?: string;
  priority?: number;
  status?: string;
  category?: string;
  categorySource?: string;
  requirement?: Requirement | null;
  path?: ServicePath | null;
  actual?: Actual | null;
  detailError?: string | null;
}

export interface SimEvent {
  eventId: string;
  type: string;
  time?: string;
  tsUs?: number;
  payload?: Record<string, unknown>;
}

export interface CandidatePath {
  pathNo?: number;
  nodes: string[];
  links: string[];
  metrics?: Record<string, unknown>;
}

export interface Snapshot {
  health: string;
  received_at: string;
  instance_id: string | null;
  scenario_id: string | null;
  sim_time_us: number | null;
  errors: string[];
  nodes: Node[];
  links: Link[];
  services: Service[];
  events: SimEvent[];
  events_cursor: number;
}
