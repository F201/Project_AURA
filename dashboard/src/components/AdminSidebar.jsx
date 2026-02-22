import { useNavigate, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
    { icon: 'chat_bubble_outline', label: 'Chat', path: '/' },
    { icon: 'dashboard', label: 'Board', path: '/admin' },
    { icon: 'settings', label: 'Setup', path: '/admin' },
]

export default function AdminSidebar() {
    const navigate = useNavigate()
    const location = useLocation()

    return (
        <aside className="w-20 lg:w-24 bg-white border-r border-slate-200 flex flex-col items-center py-8 gap-10">
            {/* Logo */}
            <div className="p-2 aura-gradient rounded-xl mb-4 shadow-lg shadow-primary/20">
                <span className="material-icons-round text-white text-3xl">blur_on</span>
            </div>

            {/* Nav */}
            <nav className="flex flex-col gap-8 flex-1">
                {NAV_ITEMS.map((item) => {
                    const isActive = item.path === location.pathname
                    return (
                        <button
                            key={item.label}
                            type="button"
                            onClick={() => navigate(item.path)}
                            className={`flex flex-col items-center gap-1 transition-colors cursor-pointer ${isActive ? 'text-primary' : 'text-slate-400 hover:text-primary'
                                }`}
                        >
                            <div className="relative">
                                <span className="material-icons-round text-2xl">{item.icon}</span>
                                {isActive && (
                                    <div className="absolute -right-1 -top-1 w-2 h-2 bg-primary rounded-full animate-pulse" />
                                )}
                            </div>
                            <span className="text-[10px] font-medium uppercase tracking-wider">{item.label}</span>
                        </button>
                    )
                })}
            </nav>

            {/* Avatar */}
            <div className="mt-auto">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white font-bold text-sm border-2 border-primary/20 p-0.5">
                    U
                </div>
            </div>
        </aside>
    )
}
