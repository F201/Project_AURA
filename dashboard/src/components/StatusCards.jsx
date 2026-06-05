import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'

export default function StatusCards() {
    const [stats, setStats] = useState({
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

    const messageCapacity = Math.min(100, Math.max(8, Math.ceil((stats.messageCount / 250) * 100)));

    const CARDS = [
        {
            label: 'System Integrity',
            icon: 'verified_user',
            value: 'Operational',
            color: 'bg-emerald-500',
            textColor: 'text-emerald-400',
            bar: 94
        },
        {
            label: 'Neural Synapse',
            icon: 'hub',
            value: stats.messageCount,
            unit: 'msgs',
            color: 'bg-primary',
            bar: messageCapacity
        },
        {
            label: 'Cognitive Depth',
            icon: 'model_training',
            value: stats.knowledgeCount,
            unit: 'kb',
            isPrimary: true,
            bar: Math.min(100, Math.max(12, stats.knowledgeCount * 5)),
            footer: 'ACTIVE VECTORS IN RAG PIPELINE'
        },
    ]

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {CARDS.map((card) => (
                <div key={card.label} className="bg-white p-6 rounded-3xl border border-black/5 shadow-xl relative overflow-hidden group hover:border-primary/20 transition-all">
                    <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                        <span className="material-icons-round text-4xl text-black">{card.icon}</span>
                    </div>

                    <div className="relative z-10 flex flex-col h-full">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-[10px] font-black text-black/40 uppercase tracking-[0.2em]">{card.label}</span>
                        </div>

                        <div className="flex items-baseline gap-2 mb-4">
                            <span className={`text-4xl font-black tracking-tighter ${card.isPrimary || card.label === 'Neural Synapse' ? 'text-primary' : (card.textColor || 'text-black')}`}>
                                {card.value}
                            </span>
                            {card.unit && <span className="text-sm text-black/30 font-black uppercase">{card.unit}</span>}
                        </div>

                        <div className="mt-auto pt-4 border-t border-black/5">
                            {/* Progress bar */}
                            {card.bar && (
                                <div className="mb-3 w-full bg-black/5 h-1 rounded-full overflow-hidden">
                                    <div
                                        className={`${card.color || 'bg-primary'} h-full transition-all duration-1000 ease-out shadow-[0_0_8px_rgba(255,126,51,0.2)]`}
                                        style={{ width: `${card.bar}%` }}
                                    />
                                </div>
                            )}

                            {/* Segmented bar */}
                            {card.segments && (
                                <div className="mb-3 flex items-center gap-1 h-1">
                                    {card.segments.map((active, i) => (
                                        <div key={i} className={`h-full w-1/4 rounded-full ${active ? 'bg-primary' : 'bg-black/10'}`} />
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

                            <p className="text-[9px] text-black/40 font-bold uppercase tracking-wider">{card.footer || 'REAL-TIME TELEMETRY FEED'}</p>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )
}
