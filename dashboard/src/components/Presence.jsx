import { useState, useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from 'react'
import { AvatarRenderer } from './AvatarRenderer'

import { getOrCreateIdentity } from '../lib/user'

export const Presence = forwardRef(({ isActive, onStatusChange, conversationId }, ref) => {
    const [status, setStatus] = useState('idle') // idle, connecting, connected, error
    const [isTalking, setIsTalking] = useState(false)
    const roomRef = useRef(null)
    const avatarRef = useRef(null)
    const audioCtxRef = useRef(null)
    const lipRafRef = useRef(null)
    const speakTimeoutRef = useRef(null)

    // Expose avatar methods to parent if needed
    useImperativeHandle(ref, () => ({
        setExpression: (expr, dur) => avatarRef.current?.setExpression(expr, dur),
        setMouthOpen: (val) => avatarRef.current?.setMouthOpen(val),
    }))

    const cleanup = useCallback(() => {
        if (lipRafRef.current) cancelAnimationFrame(lipRafRef.current)
        if (speakTimeoutRef.current) { clearTimeout(speakTimeoutRef.current); speakTimeoutRef.current = null }
        if (audioCtxRef.current) {
            if (audioCtxRef.current.state !== 'closed') audioCtxRef.current.close()
            audioCtxRef.current = null
        }
        if (roomRef.current) {
            roomRef.current.disconnect()
            roomRef.current = null
        }
        document.getElementById('presence-agent-audio')?.remove()
        setStatus('idle')
        onStatusChange?.('idle')
    }, [onStatusChange])

    useEffect(() => {
        if (!isActive) {
            cleanup()
            return
        }

        let cancelled = false
        setStatus('connecting')
        onStatusChange?.('connecting')

        const connect = async () => {
            try {
                const ctx = new AudioContext()
                audioCtxRef.current = ctx
                await ctx.resume()

                const { Room, RoomEvent, Track } = await import('livekit-client')
                const identity = getOrCreateIdentity()

                // Fetch unique room token
                const roomName = `aura-${Date.now()}`
                let tokenUrl = `http://${window.location.hostname}:8082/getToken?room=${roomName}&identity=${encodeURIComponent(identity)}`
                if (conversationId) {
                    tokenUrl += `&conversation_id=${encodeURIComponent(conversationId)}`
                }
                const res = await fetch(tokenUrl)
                if (!res.ok) throw new Error(`Token server error: ${res.status}`)
                const { token, url } = await res.json()

                if (cancelled) return

                const room = new Room()
                roomRef.current = room

                room.on(RoomEvent.TrackSubscribed, (track) => {
                    if (track.kind === Track.Kind.Audio) {
                        const el = track.attach()
                        el.id = 'presence-agent-audio'
                        document.body.appendChild(el)

                        const analyser = ctx.createAnalyser()
                        analyser.fftSize = 2048
                        const src = ctx.createMediaStreamSource(new MediaStream([track.mediaStreamTrack]))
                        src.connect(analyser)

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
                                if (speakTimeoutRef.current) clearTimeout(speakTimeoutRef.current)
                                setIsTalking(true)
                                avatarRef.current?.setSpeaking(true)
                            } else {
                                if (!speakTimeoutRef.current) {
                                    speakTimeoutRef.current = setTimeout(() => {
                                        setIsTalking(false)
                                        avatarRef.current?.setSpeaking(false)
                                        speakTimeoutRef.current = null
                                    }, 600)
                                }
                            }
                        }
                        tick()
                    }
                })

                room.on(RoomEvent.DataReceived, (payload) => {
                    try {
                        const msg = JSON.parse(new TextDecoder().decode(payload))
                        if (msg.type === 'expression') {
                            avatarRef.current?.setExpression(msg.expressions, msg.duration)
                        }
                    } catch { }
                })

                await room.connect(url, token)
                await room.localParticipant.setMicrophoneEnabled(true)

                if (!cancelled) {
                    setStatus('connected')
                    onStatusChange?.('connected')
                }
            } catch (err) {
                console.error('[PRESENCE] Connection error:', err)
                if (!cancelled) {
                    setStatus('error')
                    onStatusChange?.('error')
                }
            }
        }

        connect()

        return () => {
            cancelled = true
            cleanup()
        }
    }, [isActive, cleanup, onStatusChange])

    return (
        <div className={`relative transition-all duration-500 rounded-3xl overflow-hidden shadow-2xl
                        ${isActive ? 'w-full h-full' : 'w-48 h-48 opacity-40 grayscale pointer-events-none'}`}>

            {/* Background Glow */}
            <div className={`absolute inset-0 aura-gradient opacity-10 transition-opacity duration-700
                            ${isTalking ? 'opacity-30' : 'opacity-10'}`} />

            <AvatarRenderer
                ref={avatarRef}
                width={isActive ? 800 : 200}
                height={isActive ? 1200 : 300}
                style={{
                    transform: isActive ? 'scale(1)' : 'scale(0.8) translateY(10%)',
                    transition: 'transform 0.5s ease-out'
                }}
            />

            {/* Status Indicators */}
            {isActive && status === 'connecting' && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-950/40 backdrop-blur-md">
                    <div className="flex flex-col items-center gap-4">
                        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                        <span className="text-white font-bold tracking-widest animate-pulse">WAKING UP...</span>
                    </div>
                </div>
            )}
        </div>
    )
})

Presence.displayName = 'Presence'
