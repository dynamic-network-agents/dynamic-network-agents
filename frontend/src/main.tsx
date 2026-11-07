import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@/app/App'
import { Providers } from '@/app/providers'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { getEnvConfig } from '@/config/env'
import { startMockWorker } from '@/mocks/browser'
import '@/styles/global.css'

async function bootstrap() {
  // 开发态 Mock：useMock=true 时先启动 MSW worker 再渲染，保证页面请求被 Mock 拦截。
  await startMockWorker(getEnvConfig().useMock)

  const root = document.getElementById('root')
  if (!root) {
    throw new Error('未找到挂载点 #root，请检查 index.html。')
  }

  createRoot(root).render(
    <StrictMode>
      <ErrorBoundary>
        <Providers>
          <App />
        </Providers>
      </ErrorBoundary>
    </StrictMode>,
  )
}

void bootstrap()
