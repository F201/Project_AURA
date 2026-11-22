import { useEffect, useState } from 'react'
import {
  Bell,
  Brain,
  Eye,
  FolderOpen,
  Heart,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  Volume2,
  X,
} from 'lucide-react'
import { CompanionState, MemoryItem, Model3DItem, ReminderItem, UserProfile } from '../types'

interface Props {
  open: boolean
  backendHttp: string
  state: CompanionState
  profile: UserProfile | null
  memories: MemoryItem[]
  reminders: ReminderItem[]
  voices: string[]
  models3D: Model3DItem[]
  selectedModel3D: string | null
  onSelectModel3D: (url: string) => void
  onRefreshModels3D: () => void
  onRefreshVoices: () => void
  onSetVolume: (vol: number) => void
  initialVolume: number
  onSetOutputDevice: (deviceId: string) => void
  initialOutputDevice: string
  avatarScale: number
  onSetAvatarScale: (scale: number) => void
  onTriggerExpression: (names: string[], duration: number) => void
  onPatchState: (patch: Partial<CompanionState>) => void
  onClose: () => void
  onHoverChange: (hover: boolean) => void
}

export function CompanionDrawer({
  open,
  backendHttp,
  state,
  profile,
  memories,
  reminders,
  voices,
  models3D,
  selectedModel3D,
  onSelectModel3D,
  onRefreshModels3D,
  onRefreshVoices,
  onSetVolume,
  initialVolume,
  onSetOutputDevice,
  initialOutputDevice,
  avatarScale,
  onSetAvatarScale,
  onTriggerExpression,
  onPatchState,
  onClose,
  onHoverChange,
}: Props) {
  const [tab, setTab] = useState<'bond' | 'vision' | 'voice'>('bond')
  const [userNameInput, setUserNameInput] = useState('')
  const [newMemory, setNewMemory] = useState('')
  const [visionImg, setVisionImg] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [volume, setVolume] = useState(initialVolume)
  const [outputDevices, setOutputDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedSink, setSelectedSink] = useState(initialOutputDevice)
  const [streamVisible, setStreamVisible] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('aura_stream_visible')
      return saved === null ? true : saved === 'true'
    } catch {
      return true
    }
  })

  useEffect(() => {
    if (open && tab === 'voice' && navigator.mediaDevices?.enumerateDevices) {
      navigator.mediaDevices
        .enumerateDevices()
        .then((list) => setOutputDevices(list.filter((d) => d.kind === 'audiooutput')))
        .catch(() => {})
    }
  }, [open, tab])

  useEffect(() => {
    if (profile?.user_name) setUserNameInput(profile.user_name)
  }, [profile?.user_name])

  const fetchPreview = async () => {
    try {
      const r = await fetch(`${backendHttp}/api/vision/preview`)
      if (r.ok) {
        const d = await r.json()
        setVisionImg(d.image || null)
      }
    } catch { /* ignore */ }
  }

  useEffect(() => {
    if (open && tab === 'vision') {
      fetchPreview()
    }
  }, [open, tab])

  if (!open) return null

  const bond = profile?.bond
  const xpPct =
    bond && bond.next_xp > bond.floor_xp
      ? Math.min(100, Math.round(((bond.xp - bond.floor_xp) / (bond.next_xp - bond.floor_xp)) * 100))
      : 100

  const saveName = async () => {
    if (!userNameInput.trim()) return
    await fetch(`${backendHttp}/api/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_name: userNameInput.trim() }),
    })
  }

  const addMemory = async () => {
    if (!newMemory.trim()) return
    await fetch(`${backendHttp}/api/memories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: newMemory.trim(), category: 'fact' }),
    })
    setNewMemory('')
  }

  const deleteMemory = async (id: number) => {
    await fetch(`${backendHttp}/api/memories/${id}`, { method: 'DELETE' })
  }

  const deleteReminder = async (id: number) => {
    await fetch(`${backendHttp}/api/reminders/${id}`, { method: 'DELETE' })
  }

  const handleUploadVoice = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await fetch(`${backendHttp}/api/voices/upload`, { method: 'POST', body: fd })
      if (r.ok) {
        await onRefreshVoices()
      }
    } finally {
      setUploading(false)
    }
  }

  return (
    <div
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
      style={{
        position: 'absolute',
        inset: '14px 14px 58px 14px',
        zIndex: 50,
        background: 'linear-gradient(160deg, rgba(16, 20, 36, 0.96), rgba(9, 11, 22, 0.96))',
        border: '1px solid rgba(129, 140, 248, 0.42)',
        borderRadius: 18,
        backdropFilter: 'blur(16px)',
        boxShadow: '0 16px 46px rgba(0,0,0,0.68)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        color: '#f1f5f9',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div style={{ display: 'flex', gap: 6 }}>
          <TabPill active={tab === 'bond'} onClick={() => setTab('bond')}>
            <Heart size={12} /> Profile & Memory
          </TabPill>
          <TabPill active={tab === 'vision'} onClick={() => setTab('vision')}>
            <Eye size={12} /> Vision
          </TabPill>
          <TabPill active={tab === 'voice'} onClick={() => setTab('voice')}>
            <Volume2 size={12} /> Voice & 3D
          </TabPill>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
            cursor: 'pointer',
          }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 13, fontSize: 12 }}>
        {tab === 'bond' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Companion Level Card */}
            <div
              style={{
                background: 'rgba(79, 70, 229, 0.16)',
                border: '1px solid rgba(129, 140, 248, 0.35)',
                borderRadius: 12,
                padding: 11,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 700, color: '#a5b4fc' }}>
                  Lv.{bond?.level ?? 1} — {bond?.title ?? 'New Companion'}
                </span>
                <span style={{ color: '#7dd3fc', fontWeight: 600 }}>{bond?.xp ?? 0} XP</span>
              </div>
              <div
                style={{
                  height: 6,
                  borderRadius: 99,
                  background: 'rgba(255,255,255,0.1)',
                  overflow: 'hidden',
                  marginBottom: 8,
                }}
              >
                <div
                  style={{
                    width: `${xpPct}%`,
                    height: '100%',
                    background: 'linear-gradient(90deg, #6366f1, #38bdf8)',
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#cbd5e1' }}>
                <span>Chats: {profile?.total_chats ?? 0}</span>
                <span>Headpats: {profile?.total_headpats ?? 0}</span>
                <span>Pokes: {profile?.total_pokes ?? 0}</span>
              </div>
            </div>

            {/* Quick Test Built-in Live2D Expressions */}
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 5 }}>
                Test Built-in Live2D Expressions
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {[
                  { label: 'Smile', names: ['SmileLock'] },
                  { label: 'Ghost', names: ['Ghost'] },
                  { label: 'Ghost Nervous', names: ['GhostChange'] },
                  { label: 'Angry', names: ['Angry'] },
                  { label: 'Sad', names: ['SadLock'] },
                  { label: 'Shadow', names: ['Shadow'] },
                  { label: 'Shocked', names: ['PupilShrink'] },
                  { label: 'Deadpan', names: ['EyeshineOff', 'Shadow'] },
                  { label: 'Tongue', names: ['tongue'] },
                  { label: 'Wink', names: ['wink'] },
                  { label: 'Blush', names: ['blush'] },
                  { label: 'Pout', names: ['pouting'] },
                  { label: 'Reset', names: ['neutral'] },
                ].map((ex) => (
                  <button
                    key={ex.label}
                    onClick={() => onTriggerExpression(ex.names, 6)}
                    style={{ ...btnSecondary, padding: '4px 8px', fontSize: 11 }}
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>

            {/* User Name */}
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>What should AURA call you?</div>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  value={userNameInput}
                  onChange={(e) => setUserNameInput(e.target.value)}
                  style={inputStyle}
                />
                <button onClick={saveName} style={btnPrimary}>
                  Save
                </button>
              </div>
            </div>

            {/* Memories */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontWeight: 600, marginBottom: 6 }}>
                <Brain size={13} color="#a5b4fc" /> Long-Term Memories ({memories.length})
              </div>
              <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                <input
                  value={newMemory}
                  onChange={(e) => setNewMemory(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addMemory()}
                  placeholder="Save a fact or preference for AURA…"
                  style={inputStyle}
                />
                <button onClick={addMemory} style={btnPrimary}>
                  <Plus size={14} />
                </button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {memories.length === 0 && (
                  <div style={{ fontSize: 11, color: '#94a3b8' }}>
                    AURA remembers details naturally as you talk, or you can add facts above.
                  </div>
                )}
                {memories.map((m) => (
                  <div
                    key={m.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                      padding: '6px 9px',
                      borderRadius: 9,
                      background: 'rgba(255,255,255,0.05)',
                    }}
                  >
                    <span style={{ fontSize: 11.5, lineHeight: 1.35 }}>
                      <strong style={{ color: '#93c5fd' }}>[{m.category}]</strong> {m.content}
                    </span>
                    <button onClick={() => deleteMemory(m.id)} style={btnGhost}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'vision' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                <span style={{ fontWeight: 600 }}>Live Vision Preview</span>
                <button onClick={fetchPreview} style={btnGhost} title="Refresh snapshot">
                  <RefreshCw size={12} />
                </button>
              </div>
              {state.blind_mode || state.privacy_paused ? (
                <div
                  style={{
                    padding: 14,
                    borderRadius: 10,
                    background: 'rgba(180, 83, 9, 0.25)',
                    border: '1px solid rgba(251, 191, 36, 0.35)',
                    fontSize: 11.5,
                  }}
                >
                  {state.blind_mode
                    ? 'Blind Mode is ON — screen capture is paused.'
                    : `Privacy Auto-Paused: ${state.privacy_reason}`}
                </div>
              ) : visionImg ? (
                <img
                  src={visionImg}
                  alt="AURA Vision"
                  style={{ width: '100%', borderRadius: 10, border: '1px solid rgba(255,255,255,0.12)' }}
                />
              ) : (
                <div style={{ fontSize: 11, color: '#94a3b8' }}>No frame captured yet.</div>
              )}
              <div style={{ fontSize: 10.5, color: '#94a3b8', marginTop: 4 }}>
                Window: {state.active_window || '—'} {state.detected_game ? `• Game: ${state.detected_game}` : ''}
              </div>
            </div>

            <ToggleRow
              label="Visible in OBS & Discord Screen Share"
              checked={streamVisible}
              onChange={(v) => {
                setStreamVisible(v)
                try {
                  localStorage.setItem('aura_stream_visible', String(v))
                } catch { /* ignore */ }
                window.auraDesktop?.setStreamVisible(v)
              }}
            />
            <ToggleRow
              label="Proactive Reactions (games, screen changes, late night)"
              checked={state.proactive_enabled}
              onChange={(v) => onPatchState({ proactive_enabled: v })}
            />
            <ToggleRow
              label="Screen Vision (multimodal LLM screen context)"
              checked={state.vision_enabled}
              onChange={(v) => onPatchState({ vision_enabled: v })}
            />
            <ToggleRow
              label="Typing Cadence & Context (memory-only, auto-pauses on passwords)"
              checked={state.typing_watcher_enabled}
              onChange={(v) => onPatchState({ typing_watcher_enabled: v })}
            />

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span>Proactive Reaction Cooldown</span>
                <span>{Math.round(state.proactive_cooldown_sec)}s</span>
              </div>
              <input
                type="range"
                min={15}
                max={300}
                step={5}
                value={state.proactive_cooldown_sec}
                onChange={(e) => onPatchState({ proactive_cooldown_sec: Number(e.target.value) })}
                style={{ width: '100%', accentColor: '#6366f1' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontWeight: 600, marginBottom: 5 }}>
                <Bell size={13} color="#7dd3fc" /> Voice Reminders ({reminders.length})
              </div>
              {reminders.length === 0 ? (
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  Say &ldquo;Remind me in 10 minutes to…&rdquo; and AURA will announce it aloud.
                </div>
              ) : (
                reminders.map((r) => (
                  <div
                    key={r.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '5px 8px',
                      borderRadius: 8,
                      background: 'rgba(255,255,255,0.05)',
                      marginBottom: 4,
                    }}
                  >
                    <span>
                      <strong style={{ color: '#7dd3fc' }}>{r.trigger_iso}</strong> — {r.text}
                    </span>
                    <button onClick={() => deleteReminder(r.id)} style={btnGhost}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {tab === 'voice' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div
              style={{
                padding: 9,
                borderRadius: 10,
                background: 'rgba(255,255,255,0.05)',
                fontSize: 11.5,
                display: 'flex',
                flexDirection: 'column',
                gap: 5,
              }}
            >
              <div>
                <strong>TTS Engine:</strong>{' '}
                <span style={{ color: state.tts_backend === 'qwen3' ? '#86efac' : '#fde68a' }}>
                  {state.tts_backend === 'qwen3'
                    ? 'Faster-Qwen3-TTS Voice Clone (CUDA)'
                    : state.tts_backend === 'loading'
                      ? 'Warming up CUDA Graphs…'
                      : 'Edge-TTS Fallback (0 VRAM)'}
                </span>
              </div>
              {state.tts_error && (
                <div style={{ fontSize: 10.5, color: '#fca5a5' }}>{state.tts_error}</div>
              )}
              {state.tts_backend !== 'qwen3' && state.tts_backend !== 'loading' && (
                <button
                  onClick={() => fetch(`${backendHttp}/api/tts/reload`, { method: 'POST' })}
                  style={{ ...btnPrimary, alignSelf: 'flex-start', marginTop: 2 }}
                >
                  Retry Qwen3 Voice Clone
                </button>
              )}
              <div>
                <strong>STT Engine:</strong>{' '}
                <span style={{ color: state.stt_ready ? '#86efac' : '#fde68a' }}>
                  {state.stt_ready ? 'faster-whisper Local CPU (0 VRAM)' : 'Loading on CPU…'}
                </span>
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Mic Trigger Mode</div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  onClick={() => onPatchState({ mic_mode: 'always' })}
                  style={state.mic_mode === 'always' ? btnPrimary : btnSecondary}
                >
                  Always Listening
                </button>
                <button
                  onClick={() => onPatchState({ mic_mode: 'wake' })}
                  style={state.mic_mode === 'wake' ? btnPrimary : btnSecondary}
                  title="Only replies when you say 'AURA' — ideal when talking to friends on Discord"
                >
                  Wake Word (&ldquo;AURA&rdquo;)
                </button>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span>Voice Volume</span>
                <span>{Math.round(volume * 100)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={1.2}
                step={0.05}
                value={volume}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setVolume(v)
                  onSetVolume(v)
                }}
                style={{ width: '100%', accentColor: '#6366f1' }}
              />
            </div>

            {outputDevices.length > 0 && (
              <div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Audio Output Device</div>
                <select
                  value={selectedSink}
                  onChange={(e) => {
                    setSelectedSink(e.target.value)
                    onSetOutputDevice(e.target.value)
                  }}
                  style={{ ...inputStyle, width: '100%' }}
                >
                  <option value="" style={{ background: '#0f172a' }}>
                    System Default
                  </option>
                  {outputDevices.map((d) => (
                    <option key={d.deviceId} value={d.deviceId} style={{ background: '#0f172a' }}>
                      {d.label || `Output ${d.deviceId.slice(0, 6)}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span>Streaming Chunk Size (lower = faster TTFA)</span>
                <span>{state.tts_chunk_size} steps (~{Math.round(state.tts_chunk_size * 83)}ms audio)</span>
              </div>
              <input
                type="range"
                min={3}
                max={10}
                value={state.tts_chunk_size}
                onChange={(e) => onPatchState({ tts_chunk_size: Number(e.target.value) })}
                style={{ width: '100%', accentColor: '#6366f1' }}
              />
            </div>

            <div>
              <div style={{ fontWeight: 600, marginBottom: 5 }}>Voice Clone Reference</div>
              <select
                value={state.tts_voice_file}
                onChange={(e) => onPatchState({ tts_voice_file: e.target.value })}
                style={{ ...inputStyle, width: '100%', marginBottom: 7 }}
              >
                {voices.map((v) => (
                  <option key={v} value={v} style={{ background: '#0f172a' }}>
                    {v}
                  </option>
                ))}
              </select>
              <div style={{ display: 'flex', gap: 6 }}>
                <label
                  style={{
                    ...btnPrimary,
                    flex: 1,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 5,
                    cursor: 'pointer',
                  }}
                >
                  <Upload size={12} />
                  {uploading ? 'Uploading…' : 'Upload Voice .wav / .pt'}
                  <input type="file" accept=".wav,.pt,.mp3,.flac" onChange={handleUploadVoice} hidden />
                </label>
                <button
                  onClick={() => window.auraDesktop?.openFolder('voice')}
                  style={btnSecondary}
                  title="Open voice folder"
                >
                  <FolderOpen size={13} />
                </button>
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Voice Language</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {(['English', 'Japanese', 'Auto'] as const).map((lang) => (
                  <button
                    key={lang}
                    onClick={() => onPatchState({ tts_language: lang })}
                    style={state.tts_language === lang ? btnPrimary : btnSecondary}
                  >
                    {lang}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                <span style={{ fontWeight: 600 }}>3D VRM / GLB Models ({models3D.length})</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={onRefreshModels3D} style={btnGhost} title="Rescan 3D folder">
                    <RefreshCw size={12} />
                  </button>
                  <button
                    onClick={() => window.auraDesktop?.openFolder('3d')}
                    style={btnGhost}
                    title="Open 3D folder"
                  >
                    <FolderOpen size={12} />
                  </button>
                </div>
              </div>
              {models3D.length === 0 ? (
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  Drop a <code>.vrm</code> or <code>.glb</code> into the 3D folder, then click Rescan and toggle the 3D icon.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {models3D.map((m) => (
                    <button
                      key={m.url}
                      onClick={() => onSelectModel3D(m.url)}
                      style={{
                        ...(selectedModel3D === m.url ? btnPrimary : btnSecondary),
                        textAlign: 'left',
                      }}
                    >
                      {m.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                <span style={{ fontWeight: 600 }}>Avatar Size (or Scroll Wheel)</span>
                <span>{Math.round(avatarScale * 100)}%</span>
              </div>
              <input
                type="range"
                min={0.4}
                max={1.75}
                step={0.05}
                value={avatarScale}
                onChange={(e) => onSetAvatarScale(Number(e.target.value))}
                style={{ width: '100%', accentColor: '#6366f1', marginBottom: 6 }}
              />
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={() => onSetAvatarScale(0.55)} style={btnSecondary}>
                  Compact
                </button>
                <button onClick={() => onSetAvatarScale(0.9)} style={btnSecondary}>
                  Full Body
                </button>
                <button onClick={() => onSetAvatarScale(1.45)} style={btnSecondary}>
                  Close-Up
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TabPill({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 9px',
        borderRadius: 99,
        fontSize: 11.5,
        fontWeight: 600,
        cursor: 'pointer',
        border: active ? '1px solid rgba(56, 189, 248, 0.55)' : '1px solid transparent',
        background: active ? 'rgba(79, 70, 229, 0.4)' : 'rgba(255,255,255,0.05)',
        color: active ? '#bae6fd' : '#cbd5e1',
      }}
    >
      {children}
    </button>
  )
}

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (val: boolean) => void
}) {
  return (
    <label
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
        padding: '6px 9px',
        borderRadius: 9,
        background: 'rgba(255,255,255,0.04)',
        cursor: 'pointer',
      }}
    >
      <span style={{ fontSize: 11.5 }}>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ accentColor: '#6366f1', width: 15, height: 15 }}
      />
    </label>
  )
}

const inputStyle: React.CSSProperties = {
  flex: 1,
  background: 'rgba(255,255,255,0.07)',
  border: '1px solid rgba(255,255,255,0.14)',
  borderRadius: 8,
  padding: '5px 8px',
  color: '#f8fafc',
  fontSize: 12,
  outline: 'none',
}

const btnPrimary: React.CSSProperties = {
  background: '#4f46e5',
  border: 'none',
  borderRadius: 8,
  padding: '5px 10px',
  color: '#fff',
  fontSize: 11.5,
  fontWeight: 600,
  cursor: 'pointer',
}

const btnSecondary: React.CSSProperties = {
  background: 'rgba(255,255,255,0.08)',
  border: '1px solid rgba(255,255,255,0.14)',
  borderRadius: 8,
  padding: '5px 10px',
  color: '#e2e8f0',
  fontSize: 11.5,
  cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#94a3b8',
  cursor: 'pointer',
  padding: 3,
}
