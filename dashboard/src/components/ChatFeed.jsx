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

                    {/* Bubble Container */}
                    <div className="flex flex-col gap-2 max-w-[70%]">
                        {/* Tool Usage Indicator */}
                        {msg.tools_used && msg.tools_used.map((tool, idx) => (
                            <div key={`tool-${idx}`} className="px-3 py-2 bg-indigo-50/80 backdrop-blur-sm border border-indigo-100 rounded-xl text-xs text-indigo-700 flex items-center gap-2 shadow-sm">
                                <span className="material-icons-round text-[16px] text-indigo-500">travel_explore</span>
                                <div>
                                    <span className="font-medium mr-1 font-mono">{tool.name}</span>
                                    <span className="opacity-80 truncate max-w-[200px] inline-block align-bottom">{JSON.stringify(tool.args.query || tool.args)}</span>
                                </div>
                            </div>
                        ))}

                        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.role === 'user'
                            ? 'bg-slate-800 text-white rounded-tr-md'
                            : 'bg-white border border-slate-100 text-slate-700 rounded-tl-md shadow-sm'
                            }`}>
                            {msg.content}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )
}
