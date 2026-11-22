import { Sparkles, VolumeX, X } from 'lucide-react'

interface Props {
  text: string
  visible: boolean
  isThinking: boolean
  isSpeaking: boolean
  toolNote: string
  onClose: () => void
  onInterrupt: () => void
  onHoverChange: (hover: boolean) => void
}

export function SpeechBubble({
  text,
  visible,
  isThinking,
  isSpeaking,
  toolNote,
  onClose,
  onInterrupt,
  onHoverChange,
}: Props) {
  if ((!visible && !isThinking) || (!text.trim() && !isThinking)) return null

  return (
    <div
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
      style={{
        position: 'absolute',
        top: 8,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 'min(360px, calc(100% - 36px))',
        zIndex: 35,
        background: 'linear-gradient(145deg, rgba(17, 20, 36, 0.92), rgba(11, 13, 24, 0.92))',
        border: '1px solid rgba(129, 140, 248, 0.45)',
        borderRadius: 16,
        padding: '10px 13px',
        boxShadow: '0 10px 28px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(199, 210, 254, 0.14)',
        backdropFilter: 'blur(12px)',
        color: '#f8fafc',
        transition: 'opacity 0.22s ease',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 4,
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Sparkles size={13} color="#38bdf8" />
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.6, color: '#a5b4fc' }}>
            AURA
          </span>
          {toolNote && (
            <span
              style={{
                fontSize: 10,
                padding: '1px 6px',
                borderRadius: 99,
                background: 'rgba(56, 189, 248, 0.18)',
                color: '#bae6fd',
              }}
            >
              {toolNote}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {isSpeaking && (
            <button
              onClick={onInterrupt}
              title="Stop speaking"
              style={{
                background: 'rgba(239, 68, 68, 0.22)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                color: '#fecaca',
                borderRadius: 8,
                padding: '2px 5px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <VolumeX size={12} />
            </button>
          )}
          <button
            onClick={onClose}
            title="Dismiss subtitle"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={13} />
          </button>
        </div>
      </div>

      <div style={{ fontSize: 12.5, lineHeight: 1.48, color: '#f1f5f9', maxHeight: 110, overflowY: 'auto' }}>
        {text || (isThinking ? 'Thinking…' : '')}
      </div>
    </div>
  )
}
