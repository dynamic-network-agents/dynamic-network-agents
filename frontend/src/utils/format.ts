/**
 * 展示层格式化工具（纯函数）。
 * 与 FE-004 的 DTO 单位标准化互补：本文件负责「展示成人类可读文本」，
 * 不负责把后端原始字段换算成标准单位（那在 adapter 内完成）。
 */

const MS_PER_SECOND = 1000
const MS_PER_MINUTE = 60 * MS_PER_SECOND
const MS_PER_HOUR = 60 * MS_PER_MINUTE

/** 将仿真时间（毫秒）格式化为「2h 10m 30s 500ms」样式的可读文本；为 0 时返回 "0ms"。 */
export function formatSimTimeMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) {
    throw new Error(`非法的仿真时间：${ms}`)
  }
  if (ms === 0) return '0ms'

  const hours = Math.floor(ms / MS_PER_HOUR)
  const minutes = Math.floor((ms % MS_PER_HOUR) / MS_PER_MINUTE)
  const seconds = Math.floor((ms % MS_PER_MINUTE) / MS_PER_SECOND)
  const millis = ms % MS_PER_SECOND

  const parts: string[] = []
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)
  if (seconds > 0) parts.push(`${seconds}s`)
  if (millis > 0) parts.push(`${millis}ms`)
  return parts.join(' ')
}

/** 将 0~1 的比例格式化为百分比（默认保留 1 位小数），如 0.0234 → "2.3%"。 */
export function formatPercent(ratio: number, fractionDigits = 1): string {
  if (!Number.isFinite(ratio)) {
    throw new Error(`非法的比例：${ratio}`)
  }
  return `${(ratio * 100).toFixed(fractionDigits)}%`
}
