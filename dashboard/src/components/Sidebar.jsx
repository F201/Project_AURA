export default function Sidebar({ conversations = [], activeId, onSelect, onNewChat }) {
    // Group conversations by date
    const grouped = groupByDate(conversations)

    return (
        <aside className="w-full h-full flex flex-col bg-transparent">
            {/* Header */}
            <div className="p-6">
                <div className="flex items-center gap-3 mb-8">
                    <div className="w-9 h-9 rounded-full aura-gradient flex items-center justify-center text-white shadow-lg shadow-primary/20">
                        <span className="material-icons-round text-sm">wb_sunny</span>
                    </div>
                    <span className="font-bold text-xl tracking-tight text-white/90">Project AURA</span>
                </div>

                <button
                    type="button"
                    onClick={onNewChat}
                    className="w-full py-3.5 px-4 bg-primary hover:bg-primary/90 text-white rounded-xl flex items-center justify-center gap-2 font-bold transition-all shadow-lg shadow-primary/20 group cursor-pointer"
                >
                    <span className="material-icons-round group-hover:rotate-90 transition-transform">add</span>
                    New Context
                </button>
            </div>

            {/* Conversation list */}
            <div className="flex-1 overflow-y-auto custom-scrollbar-dark px-4 space-y-8">
                {Object.entries(grouped).map(([label, convos]) => (
                    <div key={label}>
                        <h3 className="px-3 mb-4 text-[10px] font-black uppercase tracking-[0.2em] text-white/20">{label}</h3>
                        <div className="space-y-1.5">
                            {convos.map((c) => (
                                <button
                                    key={c.id}
                                    type="button"
                                    onClick={() => onSelect(c.id)}
                                    className={`w-full group flex items-center gap-3 px-3 py-3 rounded-xl transition-all text-left cursor-pointer border ${c.id === activeId
                                        ? 'bg-white/5 text-primary border-white/5 shadow-inner'
                                        : 'hover:bg-white/[0.03] text-slate-400 border-transparent hover:border-white/5'
                                        }`}
                                >
                                    <span className={`material-icons-round text-sm ${c.id === activeId ? 'text-primary' : 'text-slate-600'}`}>
                                        {c.id === activeId ? 'auto_awesome' : 'chat_bubble_outline'}
                                    </span>
                                    <span className={`text-[13px] font-semibold truncate ${c.id === activeId ? 'text-white' : ''}`}>
                                        {c.title}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                ))}

                {conversations.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10 opacity-20">
                        <span className="material-icons-round text-4xl mb-2">forum</span>
                        <p className="text-xs font-bold uppercase tracking-widest">Empty Space</p>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="p-4 mt-auto border-t border-white/5 bg-slate-950/20">
                <div className="flex items-center gap-3 p-3 rounded-2xl bg-white/[0.02]">
                    <div className="w-10 h-10 rounded-full aura-gradient flex items-center justify-center text-white font-bold text-sm shadow-md">
                        U
                    </div>
                    <div className="flex flex-col items-start overflow-hidden">
                        <span className="text-[13px] font-bold text-white truncate text-shadow-sm">Interface User</span>
                        <p className="text-[10px] font-black text-primary/60 uppercase tracking-widest">Premium Status</p>
                    </div>
                </div>
            </div>
        </aside>
    )
}

/** Group conversations by "Today", "Yesterday", "Older" */
function groupByDate(conversations) {
    const groups = {}
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today.getTime() - 86400000)

    for (const c of conversations) {
        const d = new Date(c.updated_at || c.created_at)
        let label
        if (d >= today) label = 'Today'
        else if (d >= yesterday) label = 'Yesterday'
        else label = 'Older'

        if (!groups[label]) groups[label] = []
        groups[label].push(c)
    }
    return groups
}
