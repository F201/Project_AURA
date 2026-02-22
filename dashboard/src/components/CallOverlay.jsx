import { useState, useEffect, useRef, useCallback } from 'react'

export default function CallOverlay({ onClose }) {
    const [status, setStatus] = useState('connecting')
    const [elapsed, setElapsed] = useState(0)
    const roomRef = useRef(null)
    const timerRef = useRef(null)

    // ─── Connect to LiveKit ──────────────────────
    useEffect(() => {
        let cancelled = false

        const connect = async () => {
            try {
                // Dynamically import to avoid bundling when not needed
                const { Room, RoomEvent, Track } = await import('livekit-client')

                // Fetch token from token server
                const res = await fetch('http://localhost:8082/getToken')
                if (!res.ok) throw new Error(`Token server error: ${res.status}`)
                const { token, url } = await res.json()

                if (cancelled) return

                // Connect to room
                const room = new Room()
                roomRef.current = room

                room.on(RoomEvent.TrackSubscribed, (track) => {
                    if (track.kind === Track.Kind.Audio) {
                        const el = track.attach()
                        el.id = 'aura-agent-audio'
                        document.body.appendChild(el)
                    }
                })

                room.on(RoomEvent.TrackUnsubscribed, (track) => {
                    track.detach().forEach((el) => el.remove())
                })

                await room.connect(url, token)
                await room.localParticipant.setMicrophoneEnabled(true)

                if (!cancelled) {
                    setStatus('connected')
                    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000)
                }
            } catch (err) {
                console.error('[AURA] Call connection error:', err)
                if (!cancelled) setStatus('error')
            }
        }

        connect()
        return () => {
            cancelled = true
            cleanup()
        }
    }, [])

    const cleanup = useCallback(() => {
        if (timerRef.current) clearInterval(timerRef.current)
        if (roomRef.current) {
            roomRef.current.disconnect()
            roomRef.current = null
        }
        document.getElementById('aura-agent-audio')?.remove()
    }, [])

    const handleHangup = () => {
        cleanup()
        onClose()
    }

    const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

    return (
        <div className="fixed inset-0 z-50 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col items-center justify-center">
            {/* Pulsing avatar */}
            <div className="relative mb-8">
                <div className={`w-32 h-32 rounded-full aura-gradient flex items-center justify-center shadow-2xl shadow-primary/30 ${status === 'connected' ? 'animate-pulse' : ''
                    }`}>
                    <span className="material-icons-round text-white text-5xl">wb_sunny</span>
                </div>
                {status === 'connected' && (
                    <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 flex gap-1">
                        {[0, 1, 2, 3, 4].map((i) => (
                            <div
                                key={i}
                                className="w-1 bg-primary rounded-full"
                                style={{
                                    height: `${12 + Math.random() * 20}px`,
                                    animation: `pulse ${0.4 + i * 0.1}s ease-in-out infinite alternate`,
                                }}
                            />
                        ))}
                    </div>
                )}
            </div>

            <h2 className="text-white text-2xl font-bold mb-1">AURA</h2>
            <p className="text-primary/80 text-sm font-medium mb-8">
                {status === 'connecting' && 'Connecting...'}
                {status === 'connected' && formatTime(elapsed)}
                {status === 'error' && 'Connection failed'}
            </p>

            {/* Hangup button */}
            <button
                type="button"
                onClick={handleHangup}
                className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center text-white shadow-lg shadow-red-500/30 transition-all cursor-pointer"
            >
                <span className="material-icons-round text-3xl">call_end</span>
            </button>
        </div>
    )
}
