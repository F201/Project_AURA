import { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabaseClient'

const LEVEL_COLORS = {
    INFO: 'text-emerald-400',
    WARN: 'text-amber-400',
    ERROR: 'text-red-400',
    SYNC: 'text-primary',
}

export default function SystemLogs() {
    const [logs, setLogs] = useState([])
    const containerRef = useRef(null)

    useEffect(() => {
        // Load initial logs
        loadLogs()

        // Subscribe to realtime inserts
        const channel = supabase
            .channel('system-logs')
            .on(
                'postgres_changes',
                { event: 'INSERT', schema: 'public', table: 'system_logs' },
                (payload) => {
                    setLogs((prev) => [...prev, payload.new])
                }
            )
            .subscribe()

        return () => { supabase.removeChannel(channel) }
    }, [])

    // Auto-scroll on new logs
    useEffect(() => {
        if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight
        }
    }, [logs])

    const loadLogs = async () => {
        const { data } = await supabase
            .from('system_logs')
            .select('*')
            .order('created_at', { ascending: true })
            .limit(50)
        if (data) setLogs(data)
    }

    const formatTime = (ts) => {
        return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }

    return (
        <div className="bg-[#121212] rounded-xl overflow-hidden border border-white/5 shadow-2xl">
            <div className="bg-[#1a1a1a] px-6 py-3 border-b border-white/5 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <span className="material-icons-round text-primary text-sm">terminal</span>
                    <span className="text-xs font-bold text-white/60 tracking-widest uppercase">
                        System Logs — Live Stream
                    </span>
                </div>
                <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                    <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                    <div className="w-2.5 h-2.5 rounded-full bg-primary/40" />
                </div>
            </div>

            <div ref={containerRef} className="p-6 h-64 overflow-y-auto font-mono text-sm space-y-2 custom-scrollbar">
                {logs.length === 0 && (
                    <p className="text-slate-500 text-center">No logs yet. Activity will appear here in real time.</p>
                )}

                {logs.map((log) => (
                    <div key={log.id} className={`flex gap-4 ${log.level === 'SYNC' ? 'terminal-text' : ''}`}>
                        <span className="text-primary/60 font-medium whitespace-nowrap">
                            [{formatTime(log.created_at)}]
                        </span>
                        <span className={LEVEL_COLORS[log.level] || 'text-slate-300'}>
                            {log.level}:
                        </span>
                        <span className={log.level === 'SYNC' ? 'text-white' : 'text-slate-300'}>
                            {log.message}
                        </span>
                    </div>
                ))}

                {/* Blinking cursor */}
                <div className="flex gap-4 animate-pulse">
                    <span className="text-primary font-bold">_</span>
                </div>
            </div>
        </div>
    )
}
