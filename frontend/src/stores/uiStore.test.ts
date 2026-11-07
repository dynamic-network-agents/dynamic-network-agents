import { beforeEach, describe, expect, it } from 'vitest'
import {
  selectDisplayPrefs,
  selectSelectedFlowId,
  selectSelectedLinkId,
  selectSelectedNodeId,
  selectWsStatus,
  useUiStore,
} from './uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    useUiStore.setState({
      selectedNodeId: null,
      selectedLinkId: null,
      selectedFlowId: null,
      wsStatus: 'idle',
      displayPrefs: {},
    })
  })

  it('初始选择为空、wsStatus idle', () => {
    const s = useUiStore.getState()
    expect(s.selectedNodeId).toBeNull()
    expect(s.selectedLinkId).toBeNull()
    expect(s.selectedFlowId).toBeNull()
    expect(selectWsStatus(s)).toBe('idle')
    expect(s.displayPrefs).toEqual({})
  })

  it('选择与清除', () => {
    useUiStore.getState().selectNode('N1')
    useUiStore.getState().selectLink('L1')
    useUiStore.getState().selectFlow('F1')
    expect(selectSelectedNodeId(useUiStore.getState())).toBe('N1')
    expect(selectSelectedLinkId(useUiStore.getState())).toBe('L1')
    expect(selectSelectedFlowId(useUiStore.getState())).toBe('F1')

    useUiStore.getState().clearSelection()
    expect(useUiStore.getState().selectedNodeId).toBeNull()
    expect(useUiStore.getState().selectedLinkId).toBeNull()
    expect(useUiStore.getState().selectedFlowId).toBeNull()
  })

  it('setWsStatus 更新连接状态', () => {
    useUiStore.getState().setWsStatus('open')
    expect(useUiStore.getState().wsStatus).toBe('open')
  })

  it('setDisplayPref 不可变更新、保留已有键', () => {
    useUiStore.getState().setDisplayPref('theme', 'dark')
    const first = useUiStore.getState().displayPrefs
    useUiStore.getState().setDisplayPref('density', 'compact')
    const second = useUiStore.getState().displayPrefs
    expect(first).toEqual({ theme: 'dark' })
    expect(second).toEqual({ theme: 'dark', density: 'compact' })
    expect(second).not.toBe(first)
    expect(selectDisplayPrefs(useUiStore.getState())).toEqual({ theme: 'dark', density: 'compact' })
  })
})
