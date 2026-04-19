export default function ChatHeader({ onCallStart, isCallActive, onTuningOpen }) {
    return (
        <header className="flex items-center justify-between px-8 py-5 border-b border-slate-100 bg-white/80 backdrop-blur-md">
            <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full aura-gradient flex items-center justify-center text-white shadow-lg shadow-primary/20">
                    <span className="material-icons-round text-lg">auto_awesome</span>
                </div>
                <div>
                    <h2 className="font-bold text-lg tracking-tight text-slate-800">Project AURA</h2>
                    <p className="text-[10px] uppercase tracking-widest text-primary font-bold">
                        {isCallActive ? 'Interactive Mode' : 'Ready to Assist'}
                    </p>
                </div>
            </div>

            <div className="flex items-center gap-4">
                {/* Voice Interaction Toggle */}
                <button
                    type="button"
                    onClick={onCallStart}
                    className={`flex items-center gap-2 px-6 py-2.5 rounded-full font-bold transition-all duration-300 cursor-pointer
                                ${isCallActive
                            ? 'bg-primary text-white shadow-lg shadow-primary/40'
                            : 'bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200'}`}
                >
                    <span className={`material-icons-round text-lg ${isCallActive ? 'animate-pulse' : ''}`}>
                        {isCallActive ? 'record_voice_over' : 'forum'}
                    </span>
                    {isCallActive ? 'Interactive Session Active' : 'Interact with Project AURA'}
                </button>

                {/* Personality Tuning Toggle */}
                <button
                    type="button"
                    onClick={onTuningOpen}
                    className="w-11 h-11 flex items-center justify-center bg-slate-50 hover:bg-slate-100 text-slate-400 hover:text-primary rounded-xl border border-slate-200 transition-all cursor-pointer group"
                    title="System Dashboard"
                >
                    <span className="material-icons-round text-xl group-hover:rotate-45 transition-transform">dashboard</span>
                </button>
            </div>
        </header>
    )
}
