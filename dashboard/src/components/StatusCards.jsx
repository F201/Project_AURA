import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'

export default function StatusCards() {
    const [stats, setStats] = useState({
        uptime: '99.98%',
        vram: '42%',
        knowledgeCount: 0,
        messageCount: 0,
    })

    useEffect(() => {
        const fetchStats = async () => {
            const { count: kbCount } = await supabase.from('knowledge_base').select('*', { count: 'exact', head: true })
            const { count: msgCount } = await supabase.from('messages').select('*', { count: 'exact', head: true })
            setStats(prev => ({
                ...prev,
                knowledgeCount: kbCount || 0,
                messageCount: msgCount || 0
            }))
        }
        fetchStats()
    }, [])

    const CARDS = [
        {
            label: 'System Integrity',
            icon: 'verified_user',
            value: 'Operational',
            color: 'text-emerald-400',
            footer: `${stats.uptime} UPTIME — L4 DISTANCE: 0.02`,
            bar: 94
        },
        {
            label: 'Neural Synapse',
            icon: 'hub',
            value: stats.messageCount,
            unit: 'msgs',
            footer: 'TOTAL CONVERSATIONAL NODES',
            segments: [true, true, true, false]
        },
        {
            label: 'Cognitive Depth',
            icon: 'model_training',
            value: stats.knowledgeCount,
            unit: 'kb',
            isPrimary: true,
            footer: 'ACTIVE VECTORS IN RAG PIPELINE',
            badges: ['psychology', 'auto_stories']
        },
    ]

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {CARDS.map((card) => (
                <div key={card.label} className="bg-white/[0.03] p-6 rounded-3xl border border-white/5 shadow-2xl relative overflow-hidden group hover:border-white/10 transition-all">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <span className="material-icons-round text-4xl">{card.icon}</span>
                    </div>

                    <div className="relative z-10 flex flex-col h-full">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-[10px] font-black text-white/40 uppercase tracking-[0.2em]">{card.label}</span>
                        </div>

                        <div className="flex items-baseline gap-2 mb-4">
                            <span className={`text-4xl font-black tracking-tighter ${card.isPrimary ? 'text-primary' : (card.color || 'text-white')}`}>
                                {card.value}
                            </span>
                            {card.unit && <span className="text-sm text-white/20 font-black uppercase">{card.unit}</span>}
                        </div>

                        <div className="mt-auto pt-4 border-t border-white/5">
                            {/* Progress bar */}
                            {card.bar && (
                                <div className="mb-3 w-full bg-white/5 h-1 rounded-full overflow-hidden">
                                    <div className="bg-emerald-400 h-full shadow-[0_0_8px_rgba(52,211,153,0.5)]" style={{ width: `${card.bar}%` }} />
                                </div>
                            )}

                            {/* Segmented bar */}
                            {card.segments && (
                                <div className="mb-3 flex items-center gap-1 h-1">
                                    {card.segments.map((active, i) => (
                                        <div key={i} className={`h-full w-1/4 rounded-full ${active ? 'bg-primary' : 'bg-white/10'}`} />
                                    ))}
                                </div>
                            )}

                            {/* Badges */}
                            {card.badges && (
                                <div className="mb-3 flex items-center gap-1">
                                    {card.badges.map((icon, i) => (
                                        <div key={i} className="w-6 h-6 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                                            <span className="material-icons-round text-[12px] text-primary">{icon}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <p className="text-[9px] text-white/30 font-bold uppercase tracking-wider">{card.footer}</p>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )
}
