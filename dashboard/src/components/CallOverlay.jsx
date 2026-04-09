import { useState, useEffect, useRef, useCallback } from 'react'
import { AvatarRenderer } from './AvatarRenderer'

function getOrCreateIdentity(){
    const KEY = 'aura_user_identity'
    let id = localStorage.getItem(KEY)

    if (!id){
        id = `user-${crypto.randomUUID().slice(0,8)}`
        localStorage.setItem(KEY, id)
    }

    return id
}

export default function CallOverlay({ onClose }) {
    const [status, setStatus] = useState('connecting')
    const [elapsed, setElapsed] = useState(0)
    const roomRef    = useRef(null)
    const timerRef   = useRef(null)
    const avatarRef  = useRef(null)
    const audioCtxRef      = useRef(null)
    const analyserRef      = useRef(null)
    const lipRafRef        = useRef(null)
    const speakTimeoutRef  = useRef(null)

    // ─── Connect to LiveKit ──────────────────────
    useEffect(() => {
        let cancelled = false

        const ctx = new AudioContext()
        audioCtxRef.current = ctx
        ctx.resume().catch(() => {})

        const connect = async () => {
            try {
                // Dynamically import to avoid bundling when not needed
                const { Room, RoomEvent, Track } = await import('livekit-client')
                
                const identity = getOrCreateIdentity()

                // Fetch token from token server
                const res = await fetch(`http://${window.location.hostname}:8082/getToken?room=aura-room&identity=${encodeURIComponent(identity)}`)
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

                        const analyser = ctx.createAnalyser()
                        analyser.fftSize = 2048
                        analyser.smoothingTimeConstant = 0.8
                        const src = ctx.createMediaStreamSource(
                            new MediaStream([track.mediaStreamTrack])
                        )
                        src.connect(analyser)
                        analyserRef.current = analyser

                        const buf = new Float32Array(analyser.fftSize)
                        const tick = () => {
                            lipRafRef.current = requestAnimationFrame(tick)
                            analyser.getFloatTimeDomainData(buf)
                            let sum = 0
                            for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
                            const rms = Math.sqrt(sum / buf.length)
                            const active = rms > 0.008
                            avatarRef.current?.setMouthOpen(active ? Math.min(0.55, rms * 10) : 0)

                            // Transition to speaking state immediately on audio;
                            // debounce the return to idle so brief pauses don't flicker.
                            if (active) {
                                if (speakTimeoutRef.current) {
                                    clearTimeout(speakTimeoutRef.current)
                                    speakTimeoutRef.current = null
                                }
                                avatarRef.current?.setSpeaking(true)
                            } else if (!speakTimeoutRef.current) {
                                speakTimeoutRef.current = setTimeout(() => {
                                    avatarRef.current?.setSpeaking(false)
                                    speakTimeoutRef.current = null
                                }, 600)
                            }
                        }
                        tick()
                    }
                })

                room.on(RoomEvent.TrackUnsubscribed, (track) => {
                    track.detach().forEach((el) => el.remove())
                })

                // ── Expression events from Python avatar_bridge.py ──────────
                room.on(RoomEvent.DataReceived, (payload) => {
                    try {
                        const msg = JSON.parse(new TextDecoder().decode(payload))
                        if (msg.type === 'expression') {
                            avatarRef.current?.setExpression(msg.expressions, msg.duration)
                        }
                    } catch {
                        // malformed payload — silently ignore
                    }
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
        if (lipRafRef.current) cancelAnimationFrame(lipRafRef.current)
        if (speakTimeoutRef.current) { clearTimeout(speakTimeoutRef.current); speakTimeoutRef.current = null }
        if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null }
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

    const vw = window.innerWidth
    const vh = window.innerHeight

    return (
        // Full-screen container — avatar fills the whole background,
        // controls float as an overlay on the right side (same as AIRI).
        <div className="fixed inset-0 z-50 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">

            {/* ── Live2D Avatar — full-screen canvas ── */}
            <AvatarRenderer ref={avatarRef} width={vw} height={vh} />

            {/* ── Controls — overlaid panel, right side ── */}
            <div className="absolute right-10 top-1/2 -translate-y-1/2 flex flex-col items-center gap-6
                            bg-slate-900/60 backdrop-blur-sm rounded-2xl px-8 py-6 shadow-xl">
                <h2 className="text-white text-3xl font-bold">AURA</h2>

                <p className="text-primary/80 text-sm font-medium">
                    {status === 'connecting' && 'Connecting...'}
                    {status === 'connected'  && formatTime(elapsed)}
                    {status === 'error'      && 'Connection failed'}
                </p>

                {/* Waveform */}
                {status === 'connected' && (
                    <div className="flex gap-1">
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

                {/* Hangup */}
                <button
                    type="button"
                    onClick={handleHangup}
                    className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center text-white shadow-lg shadow-red-500/30 transition-all cursor-pointer"
                >
                    <span className="material-icons-round text-3xl">call_end</span>
                </button>
            </div>
        </div>
    )
}
