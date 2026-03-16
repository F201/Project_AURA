/**
 * StageApp — Phase 4
 * Root component for the AURA desktop overlay.
 *
 * Responsibilities:
 *  - Render Hu Tao via AvatarRenderer
 *  - Connect to the LiveKit room and receive expression events
 *  - Drive autonomous walking via PIXI.Ticker + Electron IPC window moves
 */

import { useEffect, useRef } from 'react'
import * as PIXI from 'pixi.js'
import { AvatarRenderer, AvatarHandle } from './AvatarRenderer'
import DragHandle from './DragHandle'

const LIVEKIT_URL       = import.meta.env.VITE_LIVEKIT_URL as string
const TOKEN_SERVER_PORT = import.meta.env.VITE_TOKEN_PORT ?? '8082'

export default function StageApp() {
  const avatarRef = useRef<AvatarHandle>(null)

  // ── LiveKit: audio playback + expression events ─────────────────────────
  useEffect(() => {
    let room: any = null

    async function connect() {
      try {
        const { Room, RoomEvent, Track } = await import('livekit-client')

        const res = await fetch(`http://localhost:${TOKEN_SERVER_PORT}/getToken`)
        if (!res.ok) throw new Error(`Token server error: ${res.status}`)
        const { token, url } = await res.json()

        room = new Room()

        // Play AURA's audio through local speakers
        room.on(RoomEvent.TrackSubscribed, (track: any) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach() as HTMLAudioElement
            el.id = 'aura-desktop-audio'
            document.body.appendChild(el)
          }
        })
        room.on(RoomEvent.TrackUnsubscribed, (track: any) => {
          track.detach().forEach((el: HTMLElement) => el.remove())
        })

        // Expression events from Python avatar_bridge.py
        room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
          try {
            const msg = JSON.parse(new TextDecoder().decode(payload))
            if (msg.type === 'expression') {
              avatarRef.current?.setExpression(msg.expressions, msg.duration)
            }
          } catch { /* malformed payload */ }
        })

        await room.connect(url ?? LIVEKIT_URL, token)
      } catch (err) {
        console.warn('[AURA Desktop] LiveKit connect failed:', err)
      }
    }

    connect()
    return () => {
      room?.disconnect()
      document.getElementById('aura-desktop-audio')?.remove()
    }
  }, [])

  // ── Autonomous walking via PIXI.Ticker + Electron IPC ───────────────────
  useEffect(() => {
    let targetX  = window.screen.availWidth  / 2
    let currentX = targetX
    const windowH = window.screen.availHeight

    const ticker = new PIXI.Ticker()
    ticker.add(() => {
      if (Math.abs(currentX - targetX) > 0.5) {
        currentX += (targetX - currentX) * 0.04  // smooth lerp
        window.electronAPI?.moveWindow(Math.round(currentX), windowH - 640)
      }
    })
    ticker.start()

    // Roam to a new random X position every 5–10 seconds
    const roam = setInterval(() => {
      targetX = 50 + Math.random() * (window.screen.availWidth - 500)
    }, 5000 + Math.random() * 5000)

    return () => {
      ticker.destroy()
      clearInterval(roam)
    }
  }, [])

  return (
    <div style={{
      width:      '100vw',
      height:     '100vh',
      background: 'transparent',
      overflow:   'hidden',
      position:   'relative',
    }}>
      <DragHandle />
      <AvatarRenderer ref={avatarRef} width={400} height={580} scale={0.3} />
    </div>
  )
}
