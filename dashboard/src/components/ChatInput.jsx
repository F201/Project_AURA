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
        <div className="px-8 pb-6 pt-2">
            <div className="max-w-3xl mx-auto flex items-end gap-3 p-3 bg-white border border-slate-200 rounded-2xl shadow-lg shadow-black/[0.03]">
                <textarea
                    ref={textareaRef}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a message..."
                    disabled={disabled}
                    rows={1}
                    className="flex-1 bg-transparent text-sm resize-none outline-none py-2 px-2 placeholder-slate-400 disabled:opacity-50"
                />
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!text.trim() || disabled}
                    className="flex items-center justify-center w-10 h-10 rounded-xl aura-gradient text-white transition-all disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
                >
                    <span className="material-icons-round text-lg">
                        {disabled ? 'hourglass_top' : 'arrow_upward'}
                    </span>
                </button>
            </div>
        </div>
    )
}
