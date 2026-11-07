import { useCallback, useEffect, useRef, useState } from 'react'

interface CopyButtonProps {
  /** 要复制的文本。 */
  text: string
  /** 复制前的文案。 */
  label?: string
  /** 复制成功后的文案。 */
  copiedLabel?: string
}

/**
 * 复制按钮：点击将 `text` 写入剪贴板并短暂反馈「已复制」。
 * 用于复制 linkId / requestId / traceId 等标识。
 */
export function CopyButton({ text, label = '复制', copiedLabel = '已复制' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current)
      }
    }
  }, [])

  const handleClick = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch (error) {
      console.error('[CopyButton] 复制失败', error)
      return
    }
    setCopied(true)
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
    }
    timerRef.current = window.setTimeout(() => setCopied(false), 2000)
  }, [text])

  return (
    <button type="button" onClick={handleClick} aria-label="复制到剪贴板">
      {copied ? copiedLabel : label}
    </button>
  )
}
