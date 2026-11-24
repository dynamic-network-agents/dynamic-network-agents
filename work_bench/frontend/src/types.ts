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

export interface QoSComposed {
  linkCount: number;
  delayMs?: number | null;
  jitterMs?: number | null;
  bandwidthBps?: number | null;
  packetLossRate?: number | null;
  ber?: number | null;
  missingParams: string[];
}

export interface StaticCheckItem {
  metric: string;
  required?: number | null;
  actual?: number | null;
  ok?: boolean | null;
  note?: string | null;
}

export interface StaticCheck {
  ok?: boolean | null;
  violations: string[];
  items: StaticCheckItem[];
}

export interface LinkLoad {
  linkId: string;
  flowCount: number;
  serviceCount: number;
  demandBps: number;
  capacityBps?: number | null;
  demandUtilization?: number | null;
  measuredBps?: number | null;
  measuredIsEstimate: boolean;
  flowKeys: string[];
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
  staticQoS?: QoSComposed | null;
  staticCheck?: StaticCheck | null;
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

export interface SvcMetaStatus {
  enabled: boolean;
  ok: boolean;
  count: number;
  error: string | null;
}

export interface ResourcePage {
  pages: number;
  count: number;
  complete: boolean;
}

export interface Pagination {
  links: ResourcePage;
  services: ResourcePage;
  topology_links?: number | null;
  consistent?: boolean | null;
  note?: string | null;
}

export interface Flow {
  flowKey: string;
  srcNodeId?: string | null;
  dstNodeId?: string | null;
  srcIp?: string | null;
  dstIp?: string | null;
  memberServiceIds: string[];
  memberCount: number;
  pathId?: string | null;
  links: string[];
  nodes: string[];
  pathContinuous?: boolean | null;
  direction?: string | null;
  missingLinks?: string[];
  categoryCounts?: Record<string, number>;
  qosMeetTrue: number;
  qosMeetFalse: number;
  qosMeetUnknown: number;
  staticQoS?: QoSComposed | null;
  staticOkCount: number;
  staticFailCount: number;
  staticUnknownCount: number;
}

export interface Snapshot {
  snapshot_version?: number;
  health: string;
  received_at: string;
  instance_id: string | null;
  scenario_id: string | null;
  sim_time_us: number | null;
  errors: string[];
  warnings?: string[];
  svc_meta?: SvcMetaStatus;
  pagination?: Pagination;
  last_success_at?: string | null;
  data_age_s?: number | null;
  stale_resources?: string[];
  offline?: boolean;
  nodes: Node[];
  links: Link[];
  services: Service[];
  flows?: Flow[];
  linkLoads?: LinkLoad[];
  events: SimEvent[];
  events_cursor: number;
}
