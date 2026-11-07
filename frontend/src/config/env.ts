/**
 * 环境变量统一读取入口。
 * FE-001 约定：业务代码一律通过 `getEnvConfig()` 读取配置，禁止散落使用 `import.meta.env`。
 */

export interface EnvConfig {
  appTitle: string
  apiBaseUrl: string
  useMock: boolean
}

type EnvSource = Record<string, string | undefined>

function readRequired(source: EnvSource, name: string): string {
  const value = source[name]
  if (value === undefined || value === '') {
    throw new Error(`缺少必要的环境配置：${name}。请在 .env.* 中补充该变量（参考 .env.example）。`)
  }
  return value
}

export function getEnvConfig(source: EnvSource = import.meta.env): EnvConfig {
  return {
    appTitle: readRequired(source, 'VITE_APP_TITLE'),
    apiBaseUrl: readRequired(source, 'VITE_API_BASE_URL'),
    useMock: (source['VITE_USE_MOCK'] ?? 'false') === 'true',
  }
}
