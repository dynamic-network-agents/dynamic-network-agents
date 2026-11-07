import { beforeEach, describe, expect, it } from 'vitest'
import { selectProjectId, selectRunId, selectScenarioId, useAppStore } from './appStore'

describe('appStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useAppStore.getState().resetRunContext()
  })

  it('初始为空', () => {
    const s = useAppStore.getState()
    expect(s.projectId).toBeNull()
    expect(s.scenarioId).toBeNull()
    expect(s.runId).toBeNull()
  })

  it('setProjectId / setScenarioId / setRunId 更新', () => {
    useAppStore.getState().setProjectId('P-1')
    useAppStore.getState().setScenarioId('S-1')
    useAppStore.getState().setRunId('R-1')
    const s = useAppStore.getState()
    expect(selectProjectId(s)).toBe('P-1')
    expect(selectScenarioId(s)).toBe('S-1')
    expect(selectRunId(s)).toBe('R-1')
  })

  it('resetRunContext 清空三者', () => {
    useAppStore.getState().setRunId('R-1')
    useAppStore.getState().resetRunContext()
    expect(useAppStore.getState().runId).toBeNull()
    expect(useAppStore.getState().scenarioId).toBeNull()
    expect(useAppStore.getState().projectId).toBeNull()
  })

  it('persist 仅持久化 projectId/scenarioId/runId（不落函数）', () => {
    useAppStore.getState().setProjectId('P-1')
    useAppStore.getState().setScenarioId('S-1')
    useAppStore.getState().setRunId('R-1')
    const raw = localStorage.getItem('app-context')
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw as string)
    expect(parsed.state).toEqual({ projectId: 'P-1', scenarioId: 'S-1', runId: 'R-1' })
    expect(parsed.state).not.toHaveProperty('setRunId')
  })
})
