import { useNavigate } from 'react-router-dom'

export default function ChatHeader({ onCallStart }) {
    const navigate = useNavigate()

    return (
        <header className="flex items-center justify-between px-8 py-5 border-b border-slate-100 bg-white/60 backdrop-blur">
            <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full aura-gradient flex items-center justify-center text-white shadow-md shadow-primary/20">
                    <span className="material-icons-round text-lg">wb_sunny</span>
                </div>
                <div>
                    <h2 className="font-bold text-lg tracking-tight">AURA</h2>
                    <p className="text-xs text-slate-400">Active • High Precision Mode</p>
                </div>
            </div>

            <div className="flex items-center gap-3">
                <button
                    type="button"
                    onClick={onCallStart}
                    className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-white px-5 py-2 rounded-full font-semibold shadow-md shadow-primary/20 transition-all cursor-pointer"
                >
                    <span className="material-icons-round text-lg">call</span>
                    Call Mode
                </button>
                <button
                    type="button"
                    onClick={() => navigate('/admin')}
                    className="p-2 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                    title="Admin Dashboard"
                >
                    <span className="material-icons-round text-slate-400">dashboard</span>
                </button>
            </div>
        </header>
    )
}
