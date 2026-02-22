import { useNavigate } from 'react-router-dom'

export default function Sidebar({ conversations = [], activeId, onSelect, onNewChat }) {
    const navigate = useNavigate()

    // Group conversations by date
    const grouped = groupByDate(conversations)

    return (
        <aside className="w-72 bg-white border-r border-slate-200 flex flex-col">
            {/* Header */}
            <div className="p-6">
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full aura-gradient flex items-center justify-center text-white shadow-lg shadow-primary/20">
                            <span className="material-icons-round text-sm">wb_sunny</span>
                        </div>
                        <span className="font-bold text-xl tracking-tight">AURA</span>
                    </div>
                    <button
                        type="button"
                        onClick={() => navigate('/admin')}
                        className="p-1 hover:bg-slate-100 rounded cursor-pointer"
                        title="Admin Dashboard"
                    >
                        <span className="material-icons-round text-slate-400">dashboard</span>
                    </button>
                </div>

                <button
                    type="button"
                    onClick={onNewChat}
                    className="w-full py-3 px-4 bg-primary hover:bg-primary/90 text-white rounded-lg flex items-center justify-center gap-2 font-semibold transition-all shadow-lg shadow-primary/20 group cursor-pointer"
                >
                    <span className="material-icons-round group-hover:rotate-90 transition-transform">add</span>
                    New Chat
                </button>
            </div>

            {/* Conversation list */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-4 space-y-6">
                {Object.entries(grouped).map(([label, convos]) => (
                    <div key={label}>
                        <h3 className="px-2 mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">{label}</h3>
                        <div className="space-y-1">
                            {convos.map((c) => (
                                <button
                                    key={c.id}
                                    type="button"
                                    onClick={() => onSelect(c.id)}
                                    className={`w-full group flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left cursor-pointer ${c.id === activeId
                                            ? 'bg-primary/5 text-primary border border-primary/10'
                                            : 'hover:bg-slate-50 text-slate-600 border border-transparent'
                                        }`}
                                >
                                    <span className={`material-icons-round text-sm ${c.id === activeId ? '' : 'text-slate-300'}`}>
                                        chat_bubble_outline
                                    </span>
                                    <span className="text-sm font-medium truncate">{c.title}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                ))}

                {conversations.length === 0 && (
                    <p className="text-center text-sm text-slate-400 mt-8">No conversations yet</p>
                )}
            </div>

            {/* Footer */}
            <div className="p-4 mt-auto border-t border-slate-100">
                <div className="flex items-center gap-3 p-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white font-bold text-sm">
                        U
                    </div>
                    <div className="flex flex-col items-start overflow-hidden">
                        <span className="text-sm font-bold truncate">User</span>
                        <span className="text-xs text-slate-400">Premium Plan</span>
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
