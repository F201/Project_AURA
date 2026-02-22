export default function ChatFeed({ messages = [] }) {
    if (messages.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-20 h-20 rounded-full aura-gradient flex items-center justify-center text-white mb-6 shadow-lg shadow-primary/20">
                    <span className="material-icons-round text-4xl">wb_sunny</span>
                </div>
                <h2 className="text-2xl font-bold mb-2">Hello! I'm AURA</h2>
                <p className="text-slate-400 max-w-sm">
                    Your personal AI companion. Ask me anything, or start a voice call!
                </p>
            </div>
        )
    }

    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {messages.map((msg) => (
                <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                    {/* Avatar */}
                    <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold ${msg.role === 'user'
                            ? 'bg-slate-700'
                            : 'aura-gradient shadow-sm shadow-primary/20'
                        }`}>
                        {msg.role === 'user' ? 'U' : '☀'}
                    </div>

                    {/* Bubble */}
                    <div className={`max-w-[70%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.role === 'user'
                            ? 'bg-slate-800 text-white rounded-tr-md'
                            : 'bg-white border border-slate-100 text-slate-700 rounded-tl-md shadow-sm'
                        }`}>
                        {msg.content}
                    </div>
                </div>
            ))}
        </div>
    )
}
