export interface CursorPosPayload {
  screenX: number
  screenY: number
  winX: number
  winY: number
  winW: number
  winH: number
  dispW: number
  dispH: number
}

export interface CompanionState {
  mic_muted: boolean
  mic_mode: 'always' | 'wake'
  blind_mode: boolean
  game_mode: boolean
  proactive_enabled: boolean
  vision_enabled: boolean
  typing_watcher_enabled: boolean
  privacy_paused: boolean
  privacy_reason: string
  tts_backend: 'qwen3' | 'remote' | 'edge' | 'loading' | 'off'
  tts_error: string
  tts_ready: boolean
  stt_ready: boolean
  is_speaking: boolean
  is_listening: boolean
  is_thinking: boolean
  active_window: string
  active_process: string
  detected_game: string
  tts_chunk_size: number
  tts_voice_file: string
  tts_language: string
  proactive_cooldown_sec: number
}

export interface BondInfo {
  level: number
  title: string
  xp: number
  floor_xp: number
  next_xp: number
}

export interface UserProfile {
  user_name: string
  mood: string
  total_headpats: number
  total_pokes: number
  total_chats: number
  first_met_at: number
  last_seen_at: number
  bond: BondInfo
}

export interface MemoryItem {
  id: number
  category: string
  content: string
  importance: number
  created_at: number
}

export interface ReminderItem {
  id: number
  text: string
  trigger_at: number
  trigger_iso: string
  fired: boolean
}

export interface ChatMessageItem {
  id?: number
  role: 'user' | 'assistant'
  content: string
  emotion?: string
  source?: string
  created_at?: number
}

export interface Model3DItem {
  name: string
  url: string
  ext: string
}

export interface AvatarHandle {
  setExpression(names: string[], duration: number): void
  setSpeaking(speaking: boolean): void
  setMouthOpen(value: number): void
  setCursorLook(nx: number, ny: number): void
  setDragImpulse(vx: number, vy: number): void
  setHeadpatActive(active: boolean): void
  resetNeutral(): void
}

declare global {
  interface Window {
    auraDesktop?: {
      setIgnoreMouse: (ignore: boolean) => void
      setStreamVisible: (visible: boolean) => void
      setHitBox: (box: { x: number; y: number; w: number; h: number }) => void
      startDrag: () => void
      stopDrag: () => void
      moveWindowBy: (dx: number, dy: number) => void
      moveWindowTo: (x: number, y: number) => void
      resizeWindow: (width: number, height: number) => void
      getBounds: () => Promise<{ x: number; y: number; width: number; height: number }>
      getScreenSize: () => Promise<{ width: number; height: number }>
      openFolder: (kind: '3d' | 'voice') => void
      onCursorPos: (cb: (data: CursorPosPayload) => void) => () => void
      onHotkey: (cb: (action: string) => void) => () => void
    }
  }
}
