import { useState } from 'react'
import {
  Box,
  Compass,
  Eye,
  EyeOff,
  Gamepad2,
  MessageSquare,
  Mic,
  MicOff,
  Send,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react'
import { CompanionState } from '../types'

interface Props {
  visible: boolean
  connected: boolean
  state: CompanionState
  avatarMode: '2d' | '3d'
  chatOpen: boolean
  drawerOpen: boolean
  roamEnabled: boolean
  onToggleMute: () => void
  onToggleBlind: () => void
  onToggleGameMode: () => void
  onToggleAvatarMode: () => void
  onToggleChat: () => void
  onToggleDrawer: () => void
  onToggleRoam: () => void
  onLookNow: () => void
  onSendChat: (text: string) => void
  onHoverChange: (hover: boolean) => void
}

export function ControlDock({
  visible,
  connected,
  state,
  avatarMode,
  chatOpen,
  drawerOpen,
  roamEnabled,
  onToggleMute,
  onToggleBlind,
  onToggleGameMode,
  onToggleAvatarMode,
  onToggleChat,
  onToggleDrawer,
  onToggleRoam,
  onLookNow,
  onSendChat,
  onHoverChange,
}: Props) {
  const [draft, setDraft] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const clean = draft.trim()
    if (!clean) return
    onSendChat(clean)
    setDraft('')
  }

  const showBar = visible || chatOpen || drawerOpen

  return (
    <div
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
      style={{
        position: 'absolute',
        bottom: 10,
        left: 12,
        right: 12,
        zIndex: 40,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
        opacity: showBar ? 1 : 0,
        transform: showBar ? 'translateY(0px)' : 'translateY(8px)',
        pointerEvents: showBar ? 'auto' : 'none',
        transition: 'opacity 0.2s ease, transform 0.2s ease',
      }}
    >
      {/* Status micro-pill */}
      {(state.privacy_paused || state.detected_game || !connected || state.tts_backend === 'loading' || state.tts_error) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 9px',
            borderRadius: 99,
            fontSize: 10.5,
            background: state.privacy_paused || state.tts_error
              ? 'rgba(180, 83, 9, 0.92)'
              : 'rgba(15, 18, 32, 0.88)',
            border: '1px solid rgba(165, 180, 252, 0.28)',
            color: '#e0e7ff',
            backdropFilter: 'blur(8px)',
          }}
        >
          {state.privacy_paused ? (
            <>
              <ShieldAlert size={11} />
              <span>{state.privacy_reason || 'Privacy Paused'}</span>
            </>
          ) : !connected ? (
            <span>Connecting to AURA Desktop Agent…</span>
          ) : state.tts_backend === 'loading' ? (
            <span>Warming up AURA TTS engine (CUDA)…</span>
          ) : state.tts_error ? (
            <span>{state.tts_error}</span>
          ) : (
            <>
              <Gamepad2 size={11} color="#93c5fd" />
              <span>Watching {state.detected_game}</span>
            </>
          )}
        </div>
      )}

      {/* Quick text chat input */}
      {chatOpen && (
        <form
          onSubmit={handleSubmit}
          style={{
            width: '100%',
            display: 'flex',
            gap: 6,
            background: 'rgba(15, 18, 32, 0.94)',
            border: '1px solid rgba(129, 140, 248, 0.45)',
            borderRadius: 12,
            padding: '5px 7px',
            backdropFilter: 'blur(12px)',
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Message AURA… (includes live screen context when vision is on)"
            autoFocus
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#f8fafc',
              fontSize: 12,
            }}
          />
          <button
            type="submit"
            style={{
              background: '#4f46e5',
              border: 'none',
              color: '#fff',
              borderRadius: 8,
              padding: '5px 8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <Send size={13} />
          </button>
        </form>
      )}

      {/* Main AURA Glass Pill Dock */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          padding: '5px 8px',
          borderRadius: 99,
          background: 'linear-gradient(180deg, rgba(20, 24, 42, 0.92), rgba(11, 14, 26, 0.94))',
          border: '1px solid rgba(129, 140, 248, 0.36)',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.55)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <DockBtn
          active={state.mic_muted}
          danger={state.mic_muted}
          pulse={!state.mic_muted && state.is_listening}
          title={state.mic_muted ? 'Unmute Mic (Ctrl+Shift+M)' : 'Mute Mic (Ctrl+Shift+M)'}
          onClick={onToggleMute}
        >
          {state.mic_muted ? <MicOff size={14} /> : <Mic size={14} />}
        </DockBtn>

        <DockBtn
          active={state.blind_mode}
          danger={state.blind_mode}
          title={
            state.blind_mode
              ? 'Privacy Blind Mode ON — click to resume screen vision (Ctrl+Shift+B)'
              : 'Blind / Privacy Pause (Ctrl+Shift+B)'
          }
          onClick={onToggleBlind}
        >
          {state.blind_mode ? <EyeOff size={14} /> : <Eye size={14} />}
        </DockBtn>

        <DockBtn title="Ask AURA to react to your screen right now" onClick={onLookNow}>
          <Sparkles size={14} />
        </DockBtn>

        <DockBtn active={chatOpen} title="Quick Text Chat" onClick={onToggleChat}>
          <MessageSquare size={14} />
        </DockBtn>

        <DockBtn
          active={state.game_mode}
          title={
            state.game_mode
              ? 'Game Mode ON (0 VRAM TTS) — click to restore Qwen3 Voice Clone'
              : 'Game Mode (Free GPU VRAM for heavy games)'
          }
          onClick={onToggleGameMode}
        >
          <Gamepad2 size={14} />
        </DockBtn>

        <DockBtn
          active={avatarMode === '3d'}
          title={`Switch Avatar Mode (currently ${avatarMode.toUpperCase()})`}
          onClick={onToggleAvatarMode}
        >
          <Box size={14} />
        </DockBtn>

        <DockBtn
          active={roamEnabled}
          title={roamEnabled ? 'Disable Desktop Roaming' : 'Enable Desktop Roaming'}
          onClick={onToggleRoam}
        >
          <Compass size={14} />
        </DockBtn>

        <DockBtn active={drawerOpen} title="Memory, Vision, Voice & Avatar Settings" onClick={onToggleDrawer}>
          <SlidersHorizontal size={14} />
        </DockBtn>
      </div>
    </div>
  )
}

function DockBtn({
  children,
  onClick,
  title,
  active,
  danger,
  pulse,
}: {
  children: React.ReactNode
  onClick: () => void
  title: string
  active?: boolean
  danger?: boolean
  pulse?: boolean
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 30,
        height: 30,
        borderRadius: 99,
        border: danger
          ? '1px solid rgba(248, 113, 113, 0.7)'
          : active
            ? '1px solid rgba(56, 189, 248, 0.65)'
            : '1px solid rgba(255, 255, 255, 0.1)',
        background: danger
          ? 'rgba(220, 38, 38, 0.85)'
          : active
            ? 'rgba(79, 70, 229, 0.45)'
            : 'rgba(255, 255, 255, 0.06)',
        color: danger ? '#fff' : active ? '#bae6fd' : '#e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        animation: pulse ? 'pulseGlow 1.3s infinite' : undefined,
        transition: 'all 0.16s ease',
      }}
    >
      {children}
    </button>
  )
}
