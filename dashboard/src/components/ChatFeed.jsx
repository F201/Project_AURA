export default function ChatFeed({ messages = [] }) {
    if (messages.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 animate-in fade-in zoom-in duration-700">
                <div className="w-24 h-24 rounded-full aura-gradient flex items-center justify-center text-white mb-8 shadow-2xl shadow-primary/40 relative">
                    <span className="material-icons-round text-5xl">auto_awesome</span>
                    <div className="absolute inset-0 rounded-full aura-gradient animate-ping opacity-20" />
                </div>
                <h2 className="text-3xl font-black mb-4 tracking-tight text-slate-900">Project AURA</h2>
                <p className="text-slate-500 max-w-sm font-medium leading-relaxed">
                    Advanced Universal Responsive Avatar. <br />
                    Ready for your next inquiry.
                </p>
            </div>
        )
    }

    return (
        <div className="space-y-8 pb-20">
            {messages.map((msg) => (
                <div key={msg.id} className={`flex gap-4 group ${msg.role === 'user' ? 'flex-row-reverse' : ''} animate-in slide-in-from-bottom-2 duration-300`}>
                    {/* Avatar Icon */}
                    <div className={`w-9 h-9 rounded-xl flex-shrink-0 flex items-center justify-center text-[11px] font-black transition-transform group-hover:scale-110 ${msg.role === 'user'
                        ? 'bg-slate-100 text-slate-500 border border-slate-200'
                        : 'aura-gradient text-white shadow-lg shadow-primary/20'
                        }`}>
                        {msg.role === 'user' ? 'ME' : 'AURA'}
                    </div>

                    {/* Content Column */}
                    <div className={`flex flex-col gap-3 max-w-[85%] lg:max-w-[70%] ${msg.role === 'user' ? 'items-end' : ''}`}>

                        {/* Tool Execution Details */}
                        {msg.tools_used && msg.tools_used.map((tool, idx) => (
                            <div key={`tool-${idx}`} className="px-4 py-2.5 bg-slate-50 border border-slate-100 rounded-2xl text-[11px] text-primary flex items-center gap-3 shadow-sm animate-in fade-in slide-in-from-left-2">
                                <span className="material-icons-round text-sm animate-spin-slow">api</span>
                                <div className="font-mono">
                                    <span className="font-black tracking-widest">{tool.name}</span>
                                    <span className="mx-2 text-slate-300">—</span>
                                    <span className="text-slate-500 truncate max-w-[200px] inline-block align-bottom">
                                        {typeof tool.args === 'string' ? tool.args : (tool.args.query || JSON.stringify(tool.args))}
                                    </span>
                                </div>
                            </div>
                        ))}

                        {/* Speech Bubble */}
                        <div className={`px-5 py-4 rounded-3xl text-[15px] leading-relaxed tracking-tight shadow-sm ${msg.role === 'user'
                            ? 'bg-primary text-white rounded-tr-sm'
                            : 'bg-white text-slate-800 rounded-tl-sm border border-slate-100'
                            }`}>
                            {msg.content}
                        </div>

                        {/* Emotion Tag */}
                        {msg.role === 'aura' && msg.emotion && (
                            <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-100 rounded-full w-fit">
                                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{msg.emotion}</span>
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    )
}
