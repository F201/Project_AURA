import { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Live2DRenderer } from './avatar/Live2DRenderer'
import type { AvatarHandle } from './types'

declare global {
  interface Window {
    auraAvatar?: {
      ready: boolean
      mouth(level: number): void
      expression(names: string[]): void
      zoomBy(factor: number): void
      inspectParameter?: (name: string) => number
    }
  }
}

function Avatar() {
  const model = useRef<AvatarHandle>(null)
  const pendingExpression = useRef<string[] | null>(null)
  const [zoom, setZoom] = useState(1)
  const [size, setSize] = useState(() => ({ width: innerWidth, height: innerHeight }))
  const [ready, setReady] = useState(false)
  const supportsWebGl = useRef(!!window.WebGLRenderingContext && !new URLSearchParams(location.search).has('still'))

  useEffect(() => {
    const resize = () => setSize({ width: innerWidth, height: innerHeight })
    addEventListener('resize', resize)
    window.auraAvatar = {
      ready: false,
      mouth(level) {
        model.current?.setSpeaking(level > 0)
        model.current?.setMouthOpen(level)
      },
      expression(names) {
        if (window.auraAvatar?.ready) model.current?.setExpression(names, 3)
        else pendingExpression.current = names
      },
      zoomBy(factor) {
        if (Number.isFinite(factor)) setZoom(current => Math.min(1.9, Math.max(0.65, current * factor)))
      },
    }
    return () => {
      removeEventListener('resize', resize)
      delete window.auraAvatar
    }
  }, [])

  return <>
    {!ready && <img src="./models/hutao/Icon.png" alt="AURA" />}
    {supportsWebGl.current && <Live2DRenderer
      ref={model}
      width={size.width}
      height={size.height}
      avatarScale={(size.width < size.height ? 1.18 : 1) * zoom}
      onScaleDelta={delta => setZoom(current => Math.min(1.9, Math.max(0.65, current + delta)))}
      onHoverAvatar={() => {}}
      onModelReady={readParameter => {
        if (window.auraAvatar) {
          if (new URLSearchParams(location.search).has('inspect')) window.auraAvatar.inspectParameter = readParameter
          window.auraAvatar.ready = true
        }
        if (pendingExpression.current) {
          model.current?.setExpression(pendingExpression.current, 3)
          pendingExpression.current = null
        }
        setReady(true)
      }}
      onTouch={kind => model.current?.setExpression(kind === 'headpat' ? ['SmileLock', 'blush'] : ['curious'], 2)}
    />}
  </>
}

createRoot(document.getElementById('root')!).render(<Avatar />)
