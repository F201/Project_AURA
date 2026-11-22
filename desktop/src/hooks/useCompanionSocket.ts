import { useCallback, useEffect, useRef, useState } from 'react'
import { StreamingAudioPlayer } from '../audio/StreamingAudioPlayer'
import {
  ChatMessageItem,
  CompanionState,
  MemoryItem,
  ReminderItem,
  UserProfile,
} from '../types'

const BACKEND_HTTP = 'http://127.0.0.1:8765'
const BACKEND_WS = 'ws://127.0.0.1:8765/ws'

const DEFAULT_STATE: CompanionState = {
  mic_muted: false,
  mic_mode: 'always',
  blind_mode: false,
  game_mode: false,
  proactive_enabled: true,
  vision_enabled: true,
  typing_watcher_enabled: true,
  privacy_paused: false,
  privacy_reason: '',
  tts_backend: 'loading',
  tts_error: '',
  tts_ready: false,
  stt_ready: false,
  is_speaking: false,
  is_listening: false,
  is_thinking: false,
  active_window: '',
  active_process: '',
  detected_game: '',
  tts_chunk_size: 6,
  tts_voice_file: 'aura_voice_xvec.pt',
  tts_language: 'English',
  proactive_cooldown_sec: 180,
}

export interface CompanionCallbacks {
  onExpression: (names: string[], duration: number) => void
  onMouthLevel: (level: number) => void
  onSpeakingChange: (speaking: boolean) => void
  onParticles: (kind: 'sparkle' | 'ghost') => void
}

export function useCompanionSocket(callbacks: CompanionCallbacks) {
  const [connected, setConnected] = useState(false)
  const [state, setState] = useState<CompanionState>(DEFAULT_STATE)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [reminders, setReminders] = useState<ReminderItem[]>([])
  const [history, setHistory] = useState<ChatMessageItem[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [liveSubtitle, setLiveSubtitle] = useState<string>('')
  const [lastToolNote, setLastToolNote] = useState<string>('')
  const [subtitleVisible, setSubtitleVisible] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const playerRef = useRef<StreamingAudioPlayer | null>(null)
  const cbRef = useRef(callbacks)
  cbRef.current = callbacks
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scheduleSubtitleFade = useCallback((ms = 9000) => {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
    hideTimerRef.current = setTimeout(() => setSubtitleVisible(false), ms)
  }, [])

  useEffect(() => {
    const player = new StreamingAudioPlayer(
      (lvl) => cbRef.current.onMouthLevel(lvl),
      (playing) => {
        cbRef.current.onSpeakingChange(playing)
        const ws = wsRef.current
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'playback_state', playing }))
        }
      }
    )
    playerRef.current = player

    let closed = false
    let retryTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (closed) return
      const ws = new WebSocket(BACKEND_WS)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
      }

      ws.onclose = () => {
        setConnected(false)
        if (!closed) {
          retryTimer = setTimeout(connect, 1800)
        }
      }

      ws.onerror = () => {
        ws.close()
      }

      ws.onmessage = (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          player.enqueuePcm16(ev.data)
          return
        }
        try {
          const msg = JSON.parse(ev.data)
          switch (msg.type) {
            case 'init':
              if (msg.state) setState(msg.state)
              if (msg.profile) setProfile(msg.profile)
              if (msg.memories) setMemories(msg.memories)
              if (msg.reminders) setReminders(msg.reminders)
              if (msg.history) setHistory(msg.history)
              if (msg.voices) setVoices(msg.voices)
              break
            case 'state':
              if (msg.state) setState(msg.state)
              break
            case 'profile_update':
              if (msg.profile) setProfile(msg.profile)
              break
            case 'sync_data':
              if (msg.memories) setMemories(msg.memories)
              if (msg.reminders) setReminders(msg.reminders)
              break
            case 'user_message':
              setHistory((prev) => [
                ...prev.slice(-30),
                { role: 'user', content: msg.text, source: msg.source },
              ])
              break
            case 'assistant_start':
              if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
              setLiveSubtitle('')
              setLastToolNote('')
              setSubtitleVisible(true)
              break
            case 'assistant_token':
              setLiveSubtitle((prev) => prev + (msg.text || ''))
              setSubtitleVisible(true)
              break
            case 'assistant_done':
              if (msg.text && msg.text.trim()) {
                setLiveSubtitle(msg.text)
                setHistory((prev) => [
                  ...prev.slice(-30),
                  { role: 'assistant', content: msg.text, emotion: msg.emotion },
                ])
                scheduleSubtitleFade(10000)
              } else {
                setSubtitleVisible(false)
              }
              if (msg.profile) setProfile(msg.profile)
              break
            case 'expression':
              if (Array.isArray(msg.expressions)) {
                cbRef.current.onExpression(msg.expressions, msg.duration ?? 5.5)
                if (
                  msg.expressions.includes('ghost') ||
                  msg.expressions.includes('Ghost') ||
                  msg.expressions.includes('GhostChange')
                ) {
                  cbRef.current.onParticles('ghost')
                }
                if (msg.expressions.includes('blush')) {
                  cbRef.current.onParticles('sparkle')
                }
              }
              break
            case 'particles':
              cbRef.current.onParticles(msg.kind === 'ghost' ? 'ghost' : 'sparkle')
              break
            case 'tool_event':
              setLastToolNote(`Used ${msg.name.replace(/_/g, ' ')}`)
              break
            case 'audio_start':
              player.beginStream(msg.sample_rate || 24000)
              break
            case 'audio_end':
              player.endStream()
              break
            case 'audio_stop':
              player.stop()
              setSubtitleVisible(false)
              break
            default:
              break
          }
        } catch {
          /* malformed JSON */
        }
      }
    }

    connect()

    return () => {
      closed = true
      if (retryTimer) clearTimeout(retryTimer)
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
      wsRef.current?.close()
      player.destroy()
    }
  }, [scheduleSubtitleFade])

  const sendJson = useCallback((payload: Record<string, any>) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload))
    }
  }, [])

  const sendChat = useCallback(
    (text: string, includeVision = true) => {
      sendJson({ type: 'chat', text, include_vision: includeVision })
    },
    [sendJson]
  )

  const sendTouch = useCallback(
    (kind: 'headpat' | 'poke' | 'shake') => {
      sendJson({ type: 'touch', kind })
    },
    [sendJson]
  )

  const patchState = useCallback(
    (patch: Partial<CompanionState>) => {
      setState((prev) => ({ ...prev, ...patch }))
      sendJson({ type: 'set_state', patch })
    },
    [sendJson]
  )

  const lookNow = useCallback(() => {
    sendJson({ type: 'look_now' })
  }, [sendJson])

  const interrupt = useCallback(() => {
    playerRef.current?.stop()
    sendJson({ type: 'interrupt' })
  }, [sendJson])

  const refreshVoices = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND_HTTP}/api/voices`)
      if (r.ok) {
        const d = await r.json()
        setVoices(d.files || [])
      }
    } catch { /* ignore */ }
  }, [])

  const setVolume = useCallback((vol: number) => {
    playerRef.current?.setVolume(vol)
  }, [])

  const getVolume = useCallback(() => {
    return playerRef.current?.getVolume() ?? 0.75
  }, [])

  const setOutputDevice = useCallback((deviceId: string) => {
    playerRef.current?.setOutputDevice(deviceId)
  }, [])

  const getOutputDevice = useCallback(() => {
    return playerRef.current?.getOutputDevice() ?? ''
  }, [])

  return {
    connected,
    state,
    profile,
    memories,
    reminders,
    history,
    voices,
    liveSubtitle,
    lastToolNote,
    subtitleVisible,
    setSubtitleVisible,
    sendChat,
    sendTouch,
    patchState,
    lookNow,
    interrupt,
    refreshVoices,
    setVolume,
    getVolume,
    setOutputDevice,
    getOutputDevice,
    backendHttp: BACKEND_HTTP,
  }
}
