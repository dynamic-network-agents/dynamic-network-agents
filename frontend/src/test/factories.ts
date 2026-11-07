/**
 * 测试数据工厂约定。
 * 领域对象的真实类型与字段契约以 FE-004（共享类型与 DTO）为准；本文件提供通用工厂工具
 * 与一个演示工厂，后续领域工厂在此按模块扩展（如 scenarioFactory / topologyFactory）。
 */

export type Factory<T> = (overrides?: Partial<T>) => T

/** 通用工厂：给定默认值，返回可覆盖部分字段的工厂函数。 */
export function createFactory<T extends object>(defaults: T): Factory<T> {
  return (overrides = {}) => ({ ...defaults, ...overrides })
}

// 演示工厂（字段对齐接口规范的 link 模型，最终类型由 FE-004 的 types 收敛）。
export interface SampleLink {
  linkId: string
  linkPlane: 'CONTROL' | 'DATA'
  delayMs: number
  status: 'up' | 'down'
}

export const linkFactory = createFactory<SampleLink>({
  linkId: 'link-001',
  linkPlane: 'DATA',
  delayMs: 10,
  status: 'up',
})
