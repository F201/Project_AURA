import { useEffect } from 'react'

export default function SlideOver({ isOpen, onClose, title, children }) {
    useEffect(() => {
        if (isOpen) document.body.style.overflow = 'hidden'
        else document.body.style.overflow = 'unset'
        return () => { document.body.style.overflow = 'unset' }
    }, [isOpen])

    return (
        <>
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-[60] transition-opacity duration-500
                            ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
                onClick={onClose}
            />

            {/* Panel */}
            <aside
                className={`fixed top-0 right-0 h-full w-full max-w-2xl aura-glass z-[70] transition-transform duration-500 ease-out shadow-2xl
                            ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
            >
                <div className="flex flex-col h-full bg-[#030712]/40">
                    {/* Header */}
                    <header className="flex items-center justify-between p-6 border-b border-white/10">
                        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-3">
                            <span className="w-2 h-2 rounded-full bg-primary" />
                            {title}
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-full text-slate-400 hover:text-white transition-all cursor-pointer"
                        >
                            <span className="material-icons-round">close</span>
                        </button>
                    </header>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-8 custom-scrollbar-dark">
                        {children}
                    </div>
                </div>
            </aside>
        </>
    )
}
