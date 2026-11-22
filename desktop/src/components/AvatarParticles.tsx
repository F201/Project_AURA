import { useEffect, useState } from 'react'

export interface ParticleBurst {
  id: number
  kind: 'sparkle' | 'ghost'
}

interface Particle {
  id: number
  kind: 'sparkle' | 'ghost'
  leftPct: number
  topPct: number
  delayMs: number
  size: number
}

export function AvatarParticles({ burst }: { burst: ParticleBurst | null }) {
  const [particles, setParticles] = useState<Particle[]>([])

  useEffect(() => {
    if (!burst) return
    const count = burst.kind === 'ghost' ? 4 : 6
    const created: Particle[] = Array.from({ length: count }).map((_, i) => ({
      id: burst.id * 100 + i,
      kind: burst.kind,
      leftPct: 24 + Math.random() * 52,
      topPct: 16 + Math.random() * 34,
      delayMs: i * 95,
      size: burst.kind === 'ghost' ? 22 + Math.random() * 10 : 14 + Math.random() * 8,
    }))
    setParticles((prev) => [...prev.slice(-14), ...created])

    const timer = setTimeout(() => {
      const ids = new Set(created.map((p) => p.id))
      setParticles((prev) => prev.filter((p) => !ids.has(p.id)))
    }, 2200)
    return () => clearTimeout(timer)
  }, [burst])

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        overflow: 'hidden',
        zIndex: 25,
      }}
    >
      {particles.map((p) => (
        <div
          key={p.id}
          style={{
            position: 'absolute',
            left: `${p.leftPct}%`,
            top: `${p.topPct}%`,
            fontSize: p.size,
            animation: `floatUp 1.85s ease-out ${p.delayMs}ms forwards`,
            opacity: 0,
            filter:
              p.kind === 'ghost'
                ? 'drop-shadow(0 0 8px rgba(255, 255, 255, 0.85))'
                : 'drop-shadow(0 0 6px rgba(129, 140, 248, 0.8))',
          }}
        >
          {p.kind === 'ghost' ? '👻' : '✨'}
        </div>
      ))}
    </div>
  )
}
