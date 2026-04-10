import { useState, useRef, useEffect } from 'react'

export default function ChatInput({ onSend, disabled }) {
    const [text, setText] = useState('')
    const textareaRef = useRef(null)

    // Auto-resize textarea
    useEffect(() => {
        const el = textareaRef.current
        if (el) {
            el.style.height = 'auto'
            el.style.height = Math.min(el.scrollHeight, 150) + 'px'
        }
    }, [text])

    const handleSubmit = () => {
        const trimmed = text.trim()
        if (!trimmed || disabled) return
        onSend(trimmed)
        setText('')
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }

    return (
        <div className="flex items-end gap-3 p-4 bg-white rounded-3xl border border-slate-200 shadow-xl relative group transition-all focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/5">
            <textarea
                ref={textareaRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message AURA..."
                disabled={disabled}
                rows={1}
                className="flex-1 bg-transparent text-[15px] resize-none outline-none py-2 px-3 placeholder-slate-400 text-slate-800 disabled:opacity-50"
            />

            <button
                type="button"
                onClick={handleSubmit}
                disabled={!text.trim() || disabled}
                className="flex items-center justify-center w-11 h-11 rounded-2xl aura-gradient text-white transition-all disabled:opacity-20 shadow-lg shadow-primary/20 cursor-pointer disabled:cursor-not-allowed hover:scale-105 active:scale-95"
            >
                <span className="material-icons-round">
                    {disabled ? 'hourglass_top' : 'send'}
                </span>
            </button>
        </div>
    )
}
