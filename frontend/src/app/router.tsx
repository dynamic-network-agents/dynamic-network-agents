import { createBrowserRouter } from 'react-router'
import { routeConfig } from './routes'

/**
 * 生产环境浏览器路由实例。
 * 测试使用 createMemoryRouter 消费同一个 routeConfig，避免在此创建浏览器历史。
 */
export const router = createBrowserRouter([routeConfig])
