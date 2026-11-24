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

export interface FlowCandidateCheck {
  ok: number;
  fail: number;
  unknown: number;
}

export interface FlowCandidateMember {
  serviceId: string;
  ok?: boolean | null;
  violations: string[];
}

export interface FlowCandidate {
  candidateId: string;
  pathNo?: number | null;
  links: string[];
  nodes: string[];
  linkCount: number;
  serviceIds: string[];
  missingLinks: string[];
  isCurrent: boolean;
  staticQoS?: QoSComposed | null;
  checks: FlowCandidateCheck;
  perMember: FlowCandidateMember[];
}

export interface FlowCandidatesResponse {
  flowKey: string;
  source: string;
  memberCount: number;
  currentLinks: string[];
  candidates: FlowCandidate[];
  note?: string | null;
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

export interface SimStatus {
  status: string; // running / paused / joining / finished / idle / unknown
  instanceId?: string | null;
  suiteId?: string | null;
  scenarioId?: string | null;
  scriptId?: string | null;
  t0Time?: string | null;
  t0TsUs?: number | null;
  netReadyTsUs?: number | null;
  engineState?: string | null;
  engineFired?: number | null;
  engineTotal?: number | null;
  servicesRunning?: number | null;
  serviceStates?: Record<string, number>;
  joinError?: string | null;
  noBusiness?: boolean | null;
  error?: string | null;
}

export interface LinkRisk {
  linkId: string;
  codes: string[]; // R1 断 / R2 超订 / R3 劣化
  severity: string;
  reasons: string[];
  isEstimated: boolean;
}

export interface RiskSummary {
  total: number | null;
  byCode: Record<string, number>;
  unknown: boolean;
  note?: string | null;
}

export interface OverallStatus {
  status: string; // unknown / critical / alarm / normal
  reasons: string[];
}

export interface Snapshot {
  snapshot_version?: number;
  health: string;
  received_at: string;
  instance_id: string | null;
  scenario_id: string | null;
  sim_time_us: number | null;
  sim?: SimStatus;
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
  riskLinks?: LinkRisk[];
  riskSummary?: RiskSummary;
  overallStatus?: OverallStatus;
  events: SimEvent[];
  events_cursor: number;
}
