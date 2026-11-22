import { useCallback, useEffect, useRef, useState } from 'react'
import { Live2DRenderer } from './avatar/Live2DRenderer'
import { Model3DRenderer } from './avatar/Model3DRenderer'
import { AvatarParticles, ParticleBurst } from './components/AvatarParticles'
import { CompanionDrawer } from './components/CompanionDrawer'
import { ControlDock } from './components/ControlDock'
import { SpeechBubble } from './components/SpeechBubble'
import { useCompanionSocket } from './hooks/useCompanionSocket'
import { AvatarHandle, Model3DItem } from './types'

const TOP_CLIP = 36

export default function App() {
  const avatarRef = useRef<AvatarHandle>(null)
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight })
  const [avatarScale, setAvatarScale] = useState<number>(() => {
    try {
      const saved = Number(localStorage.getItem('aura_scale'))
      if (saved >= 0.4 && saved <= 1.75) return saved
    } catch { /* ignore */ }
    return 0.85
  })
  const [avatarMode, setAvatarMode] = useState<'2d' | '3d'>('2d')
  const [models3D, setModels3D] = useState<Model3DItem[]>([])
  const [selectedModel3D, setSelectedModel3D] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [roamEnabled, setRoamEnabled] = useState(false)
  const [burst, setBurst] = useState<ParticleBurst | null>(null)
  const [cursorOverWindow, setCursorOverWindow] = useState(false)
  const [hoverFlags, setHoverFlags] = useState({
    avatar: false,
    bubble: false,
    dock: false,
    drawer: false,
  })

  // Keep window interactive while chat/drawer/dock is open; main-process 60Hz hit-test handles the avatar silhouette
  const forceInteractive = hoverFlags.bubble || hoverFlags.dock || hoverFlags.drawer || chatOpen || drawerOpen

  useEffect(() => {
    window.auraDesktop?.setIgnoreMouse(!forceInteractive)
  }, [forceInteractive])

  useEffect(() => {
    const onResize = () => setSize({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const triggerParticles = useCallback((kind: 'sparkle' | 'ghost') => {
    setBurst({ id: Date.now() + Math.random(), kind })
  }, [])

  const companion = useCompanionSocket({
    onExpression: (names, duration) => avatarRef.current?.setExpression(names, duration),
    onMouthLevel: (lvl) => avatarRef.current?.setMouthOpen(lvl),
    onSpeakingChange: (speaking) => avatarRef.current?.setSpeaking(speaking),
    onParticles: triggerParticles,
  })

  const refreshModels3D = useCallback(async () => {
    try {
      const r = await fetch(`${companion.backendHttp}/api/models3d`)
      if (r.ok) {
        const d = await r.json()
        const list: Model3DItem[] = d.models || []
        setModels3D(list)
        if (!selectedModel3D && list.length > 0) {
          setSelectedModel3D(list[0].url)
        }
      }
    } catch { /* ignore */ }
  }, [companion.backendHttp, selectedModel3D])

  useEffect(() => {
    if (companion.connected) refreshModels3D()
  }, [companion.connected, refreshModels3D])

  const updateScale = useCallback((nextOrDelta: number, isDelta = false) => {
    setAvatarScale((prev) => {
      const next = Math.max(0.4, Math.min(1.75, Number((isDelta ? prev + nextOrDelta : nextOrDelta).toFixed(2))))
      try {
        localStorage.setItem('aura_scale', String(next))
      } catch { /* ignore */ }
      return next
    })
  }, [])

  // Sync scaled avatar hit-box to Electron main process so transparent space stays click-through
  const stageH = Math.max(200, size.height - TOP_CLIP)
  const boxW = Math.round(size.width * Math.min(0.95, 0.64 * avatarScale))
  const boxH = Math.round(stageH * Math.min(0.98, 0.96 * avatarScale))
  const boxX = Math.round((size.width - boxW) / 2)
  const boxY = Math.round(avatarScale <= 1.0 ? TOP_CLIP + (stageH - boxH) : TOP_CLIP)

  useEffect(() => {
    window.auraDesktop?.setHitBox({ x: boxX, y: boxY, w: boxW, h: boxH })
  }, [boxX, boxY, boxW, boxH])

  const hitBoxRef = useRef({ x: boxX, y: boxY, w: boxW, h: boxH })
  hitBoxRef.current = { x: boxX, y: boxY, w: boxW, h: boxH }

  useEffect(() => {
    const unsub = window.auraDesktop?.onCursorPos((pt) => {
      const headX = pt.winX + pt.winW * 0.5
      const headY = pt.winY + hitBoxRef.current.y + hitBoxRef.current.h * 0.25
      const nx = Math.max(-1, Math.min(1, (pt.screenX - headX) / (pt.dispW * 0.45)))
      const ny = Math.max(-1, Math.min(1, -(pt.screenY - headY) / (pt.dispH * 0.45)))
      avatarRef.current?.setCursorLook(nx, ny)

      const hb = hitBoxRef.current
      const rx = pt.screenX - pt.winX
      const ry = pt.screenY - pt.winY
      const inside = rx >= hb.x - 10 && rx <= hb.x + hb.w + 10 && ry >= hb.y && ry <= hb.y + hb.h + 10
      setCursorOverWindow((prev) => (prev === inside ? prev : inside))
      if (!inside) {
        setHoverFlags((prev) =>
          prev.avatar || prev.dock || prev.bubble
            ? { ...prev, avatar: false, dock: false, bubble: false }
            : prev
        )
      }
    })
    return () => unsub?.()
  }, [])

  const stateRef = useRef(companion.state)
  stateRef.current = companion.state

  useEffect(() => {
    const unsub = window.auraDesktop?.onHotkey((action) => {
      if (action === 'toggle-mute') {
        companion.patchState({ mic_muted: !stateRef.current.mic_muted })
      } else if (action === 'toggle-blind') {
        companion.patchState({ blind_mode: !stateRef.current.blind_mode })
      } else if (action === 'interrupt') {
        companion.interrupt()
      } else if (action === 'toggle-drawer') {
        setDrawerOpen((o) => !o)
      }
    })
    return () => unsub?.()
  }, [companion.patchState, companion.interrupt])

  // Optional desktop roaming along the bottom of the screen
  useEffect(() => {
    if (!roamEnabled || drawerOpen || chatOpen) return
    let cancelled = false
    let rafId = 0
    let targetX = 0
    let curX = 0
    let baseY = 0
    let initialized = false

    const init = async () => {
      const [b, scr] = await Promise.all([
        window.auraDesktop?.getBounds(),
        window.auraDesktop?.getScreenSize(),
      ])
      if (cancelled || !b || !scr) return
      curX = b.x
      targetX = b.x
      baseY = b.y
      initialized = true

      const pickNext = () => {
        targetX = Math.round(40 + Math.random() * Math.max(80, scr.width - b.width - 80))
      }
      const interval = setInterval(pickNext, 9000 + Math.random() * 6000)

      const step = () => {
        if (cancelled) return
        if (initialized && !hoverFlags.avatar) {
          const diff = targetX - curX
          if (Math.abs(diff) > 1.5) {
            const dx = diff * 0.025
            curX += dx
            window.auraDesktop?.moveWindowTo(curX, baseY)
            avatarRef.current?.setDragImpulse(dx * 0.6, 0)
          }
        }
        rafId = requestAnimationFrame(step)
      }
      rafId = requestAnimationFrame(step)

      return () => clearInterval(interval)
    }

    let cleanupInterval: (() => void) | undefined
    init().then((fn) => {
      cleanupInterval = fn
    })

    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      cleanupInterval?.()
    }
  }, [roamEnabled, drawerOpen, chatOpen, hoverFlags.avatar])

  const setHover = (key: keyof typeof hoverFlags) => (val: boolean) =>
    setHoverFlags((prev) => (prev[key] === val ? prev : { ...prev, [key]: val }))

  return (
    <div
      onMouseEnter={() => setCursorOverWindow(true)}
      onMouseLeave={() => setCursorOverWindow(false)}
      onContextMenu={(e) => {
        e.preventDefault()
        setDrawerOpen((o) => !o)
      }}
      style={{
        position: 'fixed',
        top: TOP_CLIP,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'transparent',
        overflow: 'hidden',
      }}
    >
      <AvatarParticles burst={burst} />

      <SpeechBubble
        text={companion.liveSubtitle}
        visible={companion.subtitleVisible}
        isThinking={companion.state.is_thinking}
        isSpeaking={companion.state.is_speaking}
        toolNote={companion.lastToolNote}
        onClose={() => companion.setSubtitleVisible(false)}
        onInterrupt={companion.interrupt}
        onHoverChange={setHover('bubble')}
      />

      {avatarMode === '2d' ? (
        <Live2DRenderer
          ref={avatarRef}
          width={size.width}
          height={stageH}
          avatarScale={avatarScale}
          onScaleDelta={(d) => updateScale(d, true)}
          onHoverAvatar={setHover('avatar')}
          onTouch={companion.sendTouch}
        />
      ) : (
        <Model3DRenderer
          ref={avatarRef}
          modelUrl={selectedModel3D}
          width={size.width}
          height={stageH}
          onHoverAvatar={setHover('avatar')}
          onTouch={companion.sendTouch}
          onOpenFolder={() => window.auraDesktop?.openFolder('3d')}
          onSwitchTo2D={() => setAvatarMode('2d')}
        />
      )}

      <ControlDock
        visible={cursorOverWindow || hoverFlags.avatar || hoverFlags.dock}
        connected={companion.connected}
        state={companion.state}
        avatarMode={avatarMode}
        chatOpen={chatOpen}
        drawerOpen={drawerOpen}
        roamEnabled={roamEnabled}
        onToggleMute={() => companion.patchState({ mic_muted: !companion.state.mic_muted })}
        onToggleBlind={() => companion.patchState({ blind_mode: !companion.state.blind_mode })}
        onToggleGameMode={() => companion.patchState({ game_mode: !companion.state.game_mode })}
        onToggleAvatarMode={() => setAvatarMode((m) => (m === '2d' ? '3d' : '2d'))}
        onToggleChat={() => setChatOpen((o) => !o)}
        onToggleDrawer={() => setDrawerOpen((o) => !o)}
        onToggleRoam={() => setRoamEnabled((r) => !r)}
        onLookNow={companion.lookNow}
        onSendChat={(text) => companion.sendChat(text, true)}
        onHoverChange={setHover('dock')}
      />

      <CompanionDrawer
        open={drawerOpen}
        backendHttp={companion.backendHttp}
        state={companion.state}
        profile={companion.profile}
        memories={companion.memories}
        reminders={companion.reminders}
        voices={companion.voices}
        models3D={models3D}
        selectedModel3D={selectedModel3D}
        onSelectModel3D={(url) => {
          setSelectedModel3D(url)
          setAvatarMode('3d')
        }}
        onRefreshModels3D={refreshModels3D}
        onRefreshVoices={companion.refreshVoices}
        onSetVolume={companion.setVolume}
        initialVolume={companion.getVolume()}
        onSetOutputDevice={companion.setOutputDevice}
        initialOutputDevice={companion.getOutputDevice()}
        avatarScale={avatarScale}
        onSetAvatarScale={(s) => updateScale(s, false)}
        onTriggerExpression={(names, dur) => {
          avatarRef.current?.setExpression(names, dur)
          if (names.includes('Ghost') || names.includes('GhostChange')) triggerParticles('ghost')
          if (names.includes('blush')) triggerParticles('sparkle')
        }}
        onPatchState={companion.patchState}
        onClose={() => setDrawerOpen(false)}
        onHoverChange={setHover('drawer')}
      />
    </div>
  )
}
