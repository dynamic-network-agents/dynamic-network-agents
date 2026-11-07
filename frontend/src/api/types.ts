/**
 * REST API 传输层类型（对齐《前后端数据模型与接口规范 v1.0》§7）。
 *
 * 这里只承载「信封 / 分页 / 错误体」等传输协议类型；业务对象 DTO 见 `src/schemas/`。
 * 部分聚合响应的字段口径规范只给了语义、未给字段名，暂以不透明类型表示（见文末），
 * 由对应 feature 任务（Dashboard / 资源 / 路由表等）在字段确认后收敛为具体类型。
 */

/** 统一响应信封（§7.2 成功示例）；业务数据一律从 `data` 读取。 */
export interface ApiResponse<T> {
  code: string
  message: string
  data: T
  requestId?: string
  timestamp?: string
}

/** 分页载荷（§7.2/7.4：`data.items/page/pageSize/total`）。 */
export interface Page<T> {
  items: T[]
  page: number
  pageSize: number
  total: number
}

/** 字段级错误（§7.6 校验结果 `errors[]` 与 422 `details.fieldErrors` 共用：`code`/`path`/`message`）。 */
export interface FieldError {
  code: string
  path: string
  message: string
}

/** 错误响应体（§7.2 错误示例）。 */
export interface ApiErrorBody {
  code: string
  message: string
  details?: Record<string, unknown>
  requestId?: string
  timestamp?: string
}

/** 分页查询参数（§7.4，`page` 从 1 起）。 */
export interface PaginationParams {
  page?: number
  pageSize?: number
}

// ---------------------------------------------------------------------------
// 聚合响应（规范只描述内容、未给出字段名，字段口径待与官方确认）
// 后续 feature 任务（Dashboard / 资源 / 路由表等）确认字段后收敛为具体 schema。
// ---------------------------------------------------------------------------

/** 系统总览摘要（§7.11 `/dashboard/summary`）。 */
export type DashboardSummaryDto = Record<string, unknown>
/** 单业务 QoS 详情（§7.9 `/qos/flows/{flowId}`）。 */
export type QosFlowDetailDto = Record<string, unknown>
/** 业务当前路径（§7.9 `/flows/{flowId}/route`）。 */
export type FlowRouteDto = Record<string, unknown>
/** 节点邻居表（§7.8 `/nodes/{nodeId}/neighbors`）。 */
export type NodeNeighborsDto = Record<string, unknown>
/** 节点路由表（§7.8 `/nodes/{nodeId}/routes`）。 */
export type NodeRoutesDto = Record<string, unknown>
/** 仿真器能力声明（§7.7 `/simulations/capabilities`）。 */
export type SimulationCapabilitiesDto = Record<string, unknown>
/** 资源分配快照（§7.9 `/resources/allocation`）；数组或对象未定，暂不透明。 */
export type ResourceAllocationSnapshotDto = unknown
/** 资源变化记录（§7.9 `/resources/history`）；数组或分页未定，暂不透明。 */
export type ResourceHistoryDto = unknown
