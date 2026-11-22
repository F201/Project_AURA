/**
 * Live2DRenderer — Upgraded Cubism 4 Avatar Renderer for AURA Desktop
 * Features:
 *  - ParameterBus priority-resolved animation (Idle + Tracking + Interaction + Expression)
 *  - 60fps Audio RMS lip-sync
 *  - Global desktop cursor gaze tracking
 *  - Physics-sway dragging, headpat detection, cheek poke detection, scroll-wheel scaling
 */
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'

import { AvatarHandle } from '../types'
import { ParameterBus } from './ParameterBus'
import { PHYSICS_OUTPUT_PARAMS } from './PhysicsOutputParams'
import { IdleLayer } from './layers/IdleLayer'
import { TrackingLayer } from './layers/TrackingLayer'
import { ExpressionLayer } from './layers/ExpressionLayer'

Live2DModel.registerTicker(PIXI.Ticker)

const MODEL_URL = './models/hutao/Hu Tao.model3.json'

const EXPRESSION_FILES: Record<string, string> = {
  // Exact built-in Cubism 4 .exp3.json action names (used by LLM function calling)
  SmileLock: 'SmileLock.exp3.json',
  SadLock: 'SadLock.exp3.json',
  Angry: 'Angry.exp3.json',
  Ghost: 'Ghost.exp3.json',
  GhostChange: 'GhostChange.exp3.json',
  Shadow: 'Shadow.exp3.json',
  PupilShrink: 'PupilShrink.exp3.json',
  EyeshineOff: 'EyeshineOff.exp3.json',
  // Lowercase compatibility aliases
  smile: 'SmileLock.exp3.json',
  sad: 'SadLock.exp3.json',
  angry: 'Angry.exp3.json',
  ghost: 'Ghost.exp3.json',
  ghost_nervous: 'GhostChange.exp3.json',
  shadow: 'Shadow.exp3.json',
  pupil_shrink: 'PupilShrink.exp3.json',
  eyeshine_off: 'EyeshineOff.exp3.json',
}

interface Props {
  width: number
  height: number
  avatarScale: number
  onScaleDelta: (delta: number) => void
  onHoverAvatar: (hovering: boolean) => void
  onTouch: (kind: 'headpat' | 'poke' | 'shake') => void
}

export const Live2DRenderer = forwardRef<AvatarHandle, Props>(function Live2DRenderer(
  { width, height, avatarScale, onScaleDelta, onHoverAvatar, onTouch },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const appRef = useRef<PIXI.Application | null>(null)
  const modelRef = useRef<any>(null)
  const busRef = useRef<ParameterBus | null>(null)
  const idleRef = useRef<IdleLayer | null>(null)
  const trackingRef = useRef<TrackingLayer | null>(null)
  const exprRef = useRef<ExpressionLayer | null>(null)

  const speakingRef = useRef(false)
  const mouthRef = useRef(0)

  const dragStateRef = useRef({
    dragging: false,
    mode: 'none' as 'none' | 'drag' | 'headpat',
    lastScreenX: 0,
    lastScreenY: 0,
    movedDist: 0,
    shakeEnergy: 0,
    lastShakeFired: 0,
    patDistance: 0,
    lastPatFired: 0,
    downZone: 'body' as 'head' | 'face' | 'body',
  })

  useImperativeHandle(
    ref,
    () => ({
      setExpression(names, duration) {
        if (names.includes('neutral')) {
          exprRef.current?.clear()
          return
        }
        exprRef.current?.setExpression(names, duration)
      },
      setSpeaking(speaking) {
        speakingRef.current = speaking
      },
      setMouthOpen(value) {
        mouthRef.current = value
      },
      setCursorLook(nx, ny) {
        trackingRef.current?.setCursorLook(nx, ny)
      },
      setDragImpulse(vx, vy) {
        trackingRef.current?.addDragImpulse(vx, vy)
      },
      setHeadpatActive(active) {
        trackingRef.current?.setHeadpat(active)
      },
      resetNeutral() {
        exprRef.current?.clear()
      },
    }),
    []
  )

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const app = new PIXI.Application({
      backgroundAlpha: 0,
      width,
      height,
      antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true,
    })
    appRef.current = app
    container.innerHTML = ''
    container.appendChild(app.view as HTMLCanvasElement)

    let destroyed = false

    Live2DModel.from(MODEL_URL, { autoInteract: false })
      .then((model: any) => {
        if (destroyed) {
          model.destroy()
          return
        }
        modelRef.current = model
        app.stage.addChild(model)
        fitModel(model, app.screen.width, app.screen.height)

        const core = model.internalModel.coreModel
        const origCoreUpdate = core.update.bind(core)

        // Neutralize built-in expression manager so ParameterBus owns every param cleanly
        model.expression(null)

        const bus = new ParameterBus(PHYSICS_OUTPUT_PARAMS)
        const idle = new IdleLayer(bus)
        const tracking = new TrackingLayer(bus)
        const expr = new ExpressionLayer(bus, EXPRESSION_FILES)

        busRef.current = bus
        idleRef.current = idle
        trackingRef.current = tracking
        exprRef.current = expr

        let lastMs = performance.now()
        core.update = function () {
          const nowMs = performance.now()
          const elapsed = Math.min((nowMs - lastMs) / 1000, 0.1)
          lastMs = nowMs

          idle.update(elapsed, speakingRef.current)
          tracking.update(elapsed, mouthRef.current)
          expr.update(elapsed)
          bus.flush(core)
          origCoreUpdate()
        }
      })
      .catch((err: Error) => {
        console.error('[Live2DRenderer] Model load failed:', err)
      })

    return () => {
      destroyed = true
      modelRef.current = null
      appRef.current = null
      app.destroy(true, { children: true })
    }
  }, [])

  const scaleRef = useRef(avatarScale)
  scaleRef.current = avatarScale

  useEffect(() => {
    const app = appRef.current
    if (!app) return
    app.renderer.resize(width, height)
    if (modelRef.current) {
      fitModel(modelRef.current, width, height, avatarScale)
    }
  }, [width, height, avatarScale])

  function fitModel(model: any, w: number, h: number, userScale = scaleRef.current) {
    const rawH = model.internalModel?.originalHeight || model.height / (model.scale.y || 1)
    // At userScale <= 1.0: entire full-body avatar fits uncut.
    // Above 1.0 (close-up zoom): anchor top-center so zooming frames head/upper body cleanly.
    const scale = (h / rawH) * 0.96 * userScale
    model.scale.set(scale)
    if (userScale <= 1.0) {
      model.anchor.set(0.5, 1.0)
      model.position.set(w * 0.5, h * 0.99)
    } else {
      model.anchor.set(0.5, 0.0)
      model.position.set(w * 0.5, h * 0.02)
    }
  }

  function getZone(clientX: number, clientY: number): 'head' | 'face' | 'body' | 'empty' {
    const el = containerRef.current
    if (!el) return 'empty'
    const rect = el.getBoundingClientRect()
    const s = scaleRef.current
    const boxW = rect.width * Math.min(0.95, 0.62 * s)
    const boxH = rect.height * Math.min(0.98, 0.96 * s)
    const left = (rect.width - boxW) / 2
    const top = s <= 1.0 ? rect.height - boxH : 0
    const rx = (clientX - rect.left - left) / boxW
    const ry = (clientY - rect.top - top) / boxH

    if (rx < 0 || rx > 1 || ry < 0 || ry > 1) return 'empty'
    const headCut = s <= 1.0 ? 0.24 : Math.min(0.42, 0.24 * s)
    const faceCut = s <= 1.0 ? 0.44 : Math.min(0.68, 0.44 * s)
    if (ry < headCut && rx > 0.18 && rx < 0.82) return 'head'
    if (ry < faceCut && rx > 0.22 && rx < 0.78) return 'face'
    return 'body'
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const ds = dragStateRef.current
    const zone = getZone(e.clientX, e.clientY)
    onHoverAvatar(zone !== 'empty' || ds.dragging)

    if (!ds.dragging) return
    if (e.buttons === 0) {
      finishDrag(e)
      return
    }

    const dx = e.screenX - ds.lastScreenX
    const dy = e.screenY - ds.lastScreenY
    ds.lastScreenX = e.screenX
    ds.lastScreenY = e.screenY

    if (ds.mode === 'headpat') {
      ds.patDistance += Math.abs(dx) + Math.abs(dy) * 0.4
      trackingRef.current?.setHeadpat(true)
      trackingRef.current?.addDragImpulse(dx * 0.3, 0)
      const now = performance.now()
      if (ds.patDistance > 120 && now - ds.lastPatFired > 4500) {
        ds.lastPatFired = now
        ds.patDistance = 0
        onTouch('headpat')
      }
      return
    }

    if (ds.mode === 'drag') {
      ds.movedDist += Math.hypot(dx, dy)
      trackingRef.current?.addDragImpulse(dx * 0.85, dy)

      ds.shakeEnergy = ds.shakeEnergy * 0.88 + Math.abs(dx)
      const now = performance.now()
      if (ds.shakeEnergy > 155 && now - ds.lastShakeFired > 5500) {
        ds.lastShakeFired = now
        ds.shakeEnergy = 0
        onTouch('shake')
      }
    }
  }

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    const zone = getZone(e.clientX, e.clientY)
    if (zone === 'empty') return

    e.currentTarget.setPointerCapture(e.pointerId)
    const ds = dragStateRef.current
    ds.dragging = true
    ds.downZone = zone
    ds.mode = zone === 'head' && e.shiftKey ? 'headpat' : 'drag'
    ds.lastScreenX = e.screenX
    ds.lastScreenY = e.screenY
    ds.movedDist = 0
    ds.patDistance = 0
    ds.shakeEnergy = 0

    if (ds.mode === 'headpat') {
      trackingRef.current?.setHeadpat(true)
    } else {
      window.auraDesktop?.startDrag()
    }
  }

  const finishDrag = (e?: React.PointerEvent<HTMLDivElement>) => {
    const ds = dragStateRef.current
    if (!ds.dragging) return
    if (e) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId)
      } catch { /* ignore */ }
    }

    const wasClick = ds.movedDist < 6 && ds.patDistance < 25
    const zone = ds.downZone
    if (ds.mode === 'drag') {
      window.auraDesktop?.stopDrag()
    }
    ds.dragging = false
    ds.mode = 'none'
    trackingRef.current?.setHeadpat(false)

    if (wasClick) {
      if (zone === 'head') onTouch('headpat')
      else if (zone === 'face') onTouch('poke')
    }
  }

  useEffect(() => {
    const onWinUp = () => finishDrag()
    window.addEventListener('mouseup', onWinUp)
    return () => {
      window.removeEventListener('mouseup', onWinUp)
    }
  }, [])

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const zone = getZone(e.clientX, e.clientY)
    if (zone === 'empty') return
    onScaleDelta(e.deltaY < 0 ? 0.07 : -0.07)
  }

  return (
    <div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerDown={handlePointerDown}
      onPointerUp={finishDrag}
      onPointerCancel={finishDrag}
      onPointerLeave={() => {
        if (!dragStateRef.current.dragging) onHoverAvatar(false)
      }}
      onWheel={handleWheel}
      style={{
        width,
        height,
        position: 'relative',
        cursor: dragStateRef.current.dragging ? 'grabbing' : 'grab',
      }}
      title="Drag to move • Click head to pat • Click cheek to poke • Scroll to resize"
    />
  )
})
