/**
 * 查询参数序列化（§7.4 / §7.11）。
 * - 忽略 `undefined` / `null` 与非法标量值；
 * - 数组值用逗号连接（如 `experimentRunIds=ER-1,ER-2`）；
 * - 其余标量（string/number/boolean）原样保留，交由 Axios 序列化。
 * 入参用 `object` 以接受任意查询参数对象（含无索引签名的 interface/type）。
 */

export type QueryScalar = string | number | boolean

export function serializeQueryParams(params: object = {}): Record<string, QueryScalar> {
  const result: Record<string, QueryScalar> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      if (value.length > 0) result[key] = value.map(String).join(',')
      continue
    }
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      result[key] = value
    }
  }
  return result
}
