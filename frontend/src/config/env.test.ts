import { describe, expect, it } from 'vitest'
import { getEnvConfig } from './env'

describe('getEnvConfig', () => {
  it('正常解析全部配置', () => {
    const cfg = getEnvConfig({
      VITE_APP_TITLE: '测试标题',
      VITE_API_BASE_URL: 'http://localhost:8000/api',
      VITE_USE_MOCK: 'true',
    })

    expect(cfg).toEqual({
      appTitle: '测试标题',
      apiBaseUrl: 'http://localhost:8000/api',
      useMock: true,
    })
  })

  it('可选配置缺省时回退为 false', () => {
    const cfg = getEnvConfig({
      VITE_APP_TITLE: 'A',
      VITE_API_BASE_URL: 'http://x',
    })

    expect(cfg.useMock).toBe(false)
  })

  it('缺少必要配置时抛出可读错误而非白屏', () => {
    expect(() => getEnvConfig({ VITE_API_BASE_URL: 'http://x' })).toThrow(
      /缺少必要的环境配置：VITE_APP_TITLE/,
    )
  })

  it('必要配置为空字符串时同样抛出可读错误', () => {
    expect(() => getEnvConfig({ VITE_APP_TITLE: '', VITE_API_BASE_URL: 'http://x' })).toThrow(
      /缺少必要的环境配置：VITE_APP_TITLE/,
    )
  })
})
