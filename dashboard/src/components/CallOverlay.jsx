import { useState, useEffect, useRef, useCallback } from 'react'
import { AvatarRenderer } from './AvatarRenderer'

import { getOrCreateIdentity } from '../lib/user'

export default function CallOverlay({ onClose, conversationId }) {
    const [status, setStatus] = useState('connecting')
    const [elapsed, setElapsed] = useState(0)
    const roomRef = useRef(null)
    const timerRef = useRef(null)
    const avatarRef = useRef(null)
    const audioCtxRef = useRef(null)
    const analyserRef = useRef(null)
    const lipRafRef = useRef(null)
    const speakTimeoutRef = useRef(null)

    // ─── Connect to LiveKit ──────────────────────
    useEffect(() => {
        let cancelled = false

        const ctx = new AudioContext()
        audioCtxRef.current = ctx
        ctx.resume().catch(() => { })

        const connect = async () => {
            try {
                const { Room, RoomEvent, Track } = await import('livekit-client')
                const identity = getOrCreateIdentity()

                // Fetch token from token server
                let url = `http://${window.location.hostname}:8082/getToken?room=aura-room&identity=${encodeURIComponent(identity)}`
                if (conversationId) url += `&conversation_id=${encodeURIComponent(conversationId)}`

                const res = await fetch(url)
                if (!res.ok) throw new Error(`Token server error: ${res.status}`)
                const { token, url: lkUrl } = await res.json()

                if (cancelled) return

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
                        const src = ctx.createMediaStreamSource(new MediaStream([track.mediaStreamTrack]))
                        src.connect(analyser)
                        analyserRef.current = analyser

                        const buf = new Float32Array(analyser.fftSize)
                        const tick = () => {
                            if (cancelled) return
                            lipRafRef.current = requestAnimationFrame(tick)
                            analyser.getFloatTimeDomainData(buf)
                            let sum = 0
                            for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
                            const rms = Math.sqrt(sum / buf.length)
                            const active = rms > 0.008
                            avatarRef.current?.setMouthOpen(active ? Math.min(0.55, rms * 10) : 0)

                            if (active) {
                                if (speakTimeoutRef.current) { clearTimeout(speakTimeoutRef.current); speakTimeoutRef.current = null }
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

                room.on(RoomEvent.DataReceived, (payload) => {
                    try {
                        const msg = JSON.parse(new TextDecoder().decode(payload))
                        if (msg.type === 'expression') {
                            avatarRef.current?.setExpression(msg.expressions, msg.duration)
                        }
                    } catch { }
                })

                await room.connect(lkUrl, token)
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

        const handleUnload = () => { roomRef.current?.disconnect() }
        window.addEventListener('beforeunload', handleUnload)

        connect()
        return () => {
            cancelled = true
            window.removeEventListener('beforeunload', handleUnload)
            cleanup()
        }
    }, [conversationId])

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
        <div className="fixed inset-0 z-50 bg-white/95 backdrop-blur-xl animate-in fade-in duration-500">
            {/* Background Branding */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03]">
                <h1 className="text-[20vw] font-black tracking-tighter">PROJECT AURA</h1>
            </div>

            {/* ── Live2D Avatar — centered ── */}
            <div className="absolute inset-0 flex items-center justify-center">
                <AvatarRenderer ref={avatarRef} width={window.innerWidth} height={window.innerHeight} />
            </div>

            {/* ── Controls — bottom center ── */}
            <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center gap-8 w-full max-w-md px-6">
                <div className="text-center">
                    <h2 className="text-slate-900 text-3xl font-black tracking-tight mb-1 uppercase">Project AURA</h2>
                    <p className="text-primary font-black tracking-[0.3em] text-[10px] uppercase">
                        {status === 'connecting' && 'Establishing Connection...'}
                        {status === 'connected' && `Live Interaction — ${formatTime(elapsed)}`}
                        {status === 'error' && 'Neural Link Failed'}
                    </p>
                </div>

                <div className="flex items-center gap-6">
                    {/* Visualizer */}
                    {status === 'connected' && (
                        <div className="flex items-end gap-1.5 h-12">
                            {[...Array(12)].map((_, i) => (
                                <div key={i} className="w-1.5 bg-primary/20 rounded-full animate-bounce"
                                    style={{ height: `${20 + Math.random() * 80}%`, animationDuration: `${0.6 + Math.random()}s` }} />
                            ))}
                        </div>
                    )}

                    {/* Hangup */}
                    <button
                        type="button"
                        onClick={handleHangup}
                        className="w-20 h-20 rounded-full bg-slate-900 hover:bg-red-600 flex items-center justify-center text-white shadow-2xl transition-all duration-300 hover:scale-110 active:scale-95 group cursor-pointer"
                    >
                        <span className="material-icons-round text-4xl group-hover:rotate-90 transition-transform">close</span>
                    </button>

                    {/* Placeholder for future mic toggle/settings */}
                    <div className="w-12 h-12 rounded-full border border-slate-200 flex items-center justify-center text-slate-400 opacity-50">
                        <span className="material-icons-round">mic</span>
                    </div>
                </div>
            </div>
        </div>
    )
}
