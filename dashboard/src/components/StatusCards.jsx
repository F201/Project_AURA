const CARDS = [
    {
        label: 'System Status',
        icon: 'sensors',
        value: 'Operational',
        barWidth: '94%',
        footer: '99.98% UPTIME SINCE DEPLOY',
    },
    {
        label: 'Active Memory',
        icon: 'memory',
        value: '14.2',
        unit: 'GB',
        segments: [true, true, false, false],
        footer: 'USING 42% OF ALLOCATED VRAM',
    },
    {
        label: 'Current Emotion',
        icon: 'psychology',
        value: 'Analytical',
        isPrimary: true,
        footer: 'High Precision Mode Active',
        badges: ['sentiment_satisfied', 'insights'],
    },
]

export default function StatusCards() {
    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {CARDS.map((card) => (
                <div key={card.label} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                        <span className="text-slate-500 font-medium uppercase text-xs tracking-widest">{card.label}</span>
                        <span className="material-icons-round text-primary/40">{card.icon}</span>
                    </div>

                    <div className="flex items-baseline gap-2">
                        <span className={`text-4xl font-bold ${card.isPrimary ? 'text-primary' : ''}`}>{card.value}</span>
                        {card.unit && <span className="text-xl text-slate-400 font-medium">{card.unit}</span>}
                    </div>

                    {/* Progress bar */}
                    {card.barWidth && (
                        <div className="mt-4 w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                            <div className="bg-primary h-full" style={{ width: card.barWidth }} />
                        </div>
                    )}

                    {/* Segmented bar */}
                    {card.segments && (
                        <div className="mt-4 flex items-center gap-1 h-1.5">
                            {card.segments.map((active, i) => (
                                <div key={i} className={`h-full w-1/4 rounded-full ${active ? 'bg-primary' : 'bg-primary/20'}`} />
                            ))}
                        </div>
                    )}

                    {/* Badges */}
                    {card.badges && (
                        <div className="mt-4 flex items-center gap-2">
                            <div className="flex -space-x-2">
                                {card.badges.map((icon, i) => (
                                    <div key={i} className={`w-6 h-6 rounded-full flex items-center justify-center border border-white ${i === 0 ? 'bg-primary/20' : 'bg-primary'
                                        }`}>
                                        <span className={`material-icons-round text-[14px] ${i > 0 ? 'text-white' : ''}`}>{icon}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <p className="text-[10px] mt-2 text-slate-400 font-medium uppercase">{card.footer}</p>
                </div>
            ))}
        </div>
    )
}
