import { useState, useEffect } from 'react'

const PERSONALITY_SLIDERS = [
    { key: 'empathy', label: 'Empathy' },
    { key: 'humor', label: 'Humor' },
    { key: 'formality', label: 'Formality' },
]

const MODEL_OPTIONS = [
    { value: 'deepseek/deepseek-v3.2', label: 'DeepSeek V3.2' },
    { value: 'deepseek/deepseek-r1', label: 'DeepSeek R1' },
    { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'openai/gpt-4o', label: 'GPT-4o' },
    { value: 'anthropic/claude-3.5-haiku', label: 'Claude 3.5 Haiku' },
    { value: 'anthropic/claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
    { value: 'google/gemini-flash-1.5', label: 'Gemini Flash 1.5' },
]

export default function PersonalityTuner({ settings, onChange }) {
    const [draft, setDraft] = useState(null)

    useEffect(() => {
        if (settings && !draft) {
            setDraft(settings)
        }
    }, [settings])

    if (!draft) return <TunerSkeleton />

    const patch = (key, value) => {
        const updated = { ...draft, [key]: value }
        setDraft(updated)
        onChange(updated)
    }

    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
            <h3 className="text-xl font-bold mb-8 flex items-center gap-2">
                <span className="material-icons-round text-primary">tune</span>
                Personality Tuner
            </h3>

            {/* Personality Sliders */}
            <div className="space-y-6 mb-8">
                {PERSONALITY_SLIDERS.map(({ key, label }) => (
                    <div key={key} className="space-y-2">
                        <div className="flex justify-between text-sm font-medium">
                            <label className="text-slate-500">{label}</label>
                            <span className="text-primary font-bold">{draft[key] ?? 50}%</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={draft[key] ?? 50}
                            onChange={(e) => patch(key, parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-primary"
                        />
                    </div>
                ))}
            </div>

            {/* LLM Settings */}
            <div className="border-t border-slate-100 pt-6 space-y-5">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">LLM Configuration</p>

                {/* Model Selector */}
                <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Model</label>
                    <select
                        value={draft.model ?? 'deepseek/deepseek-v3.2'}
                        onChange={(e) => patch('model', e.target.value)}
                        className="w-full bg-bg-light border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    >
                        {MODEL_OPTIONS.map(({ value, label }) => (
                            <option key={value} value={value}>{label}</option>
                        ))}
                        {!MODEL_OPTIONS.find(o => o.value === draft.model) && draft.model && (
                            <option value={draft.model}>{draft.model}</option>
                        )}
                    </select>
                </div>

                {/* Temperature + Max Tokens row */}
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <div className="flex justify-between mb-1">
                            <label className="text-sm font-medium text-slate-500">Temperature</label>
                            <span className="text-xs font-bold text-primary">{(draft.temperature ?? 0.8).toFixed(1)}</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            value={draft.temperature ?? 0.8}
                            onChange={(e) => patch('temperature', parseFloat(e.target.value))}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-primary"
                        />
                        <div className="flex justify-between text-xs text-slate-400 mt-1">
                            <span>Precise</span>
                            <span>Creative</span>
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-500 mb-1">Max Tokens</label>
                        <input
                            type="number"
                            min="50"
                            max="2000"
                            step="50"
                            value={draft.max_tokens ?? 300}
                            onChange={(e) => patch('max_tokens', parseInt(e.target.value))}
                            className="w-full bg-bg-light border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                        />
                    </div>
                </div>
            </div>

            {/* System Prompt */}
            <div className="border-t border-slate-100 pt-6 mt-6">
                <label className="block text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">
                    System Prompt Override
                </label>
                <textarea
                    value={draft.system_prompt ?? ''}
                    onChange={(e) => patch('system_prompt', e.target.value)}
                    placeholder="Enter custom personality instructions... (leave empty to use AURA defaults)"
                    className="w-full h-36 bg-bg-light border border-slate-200 rounded-lg p-4 font-mono text-sm focus:ring-1 focus:ring-primary focus:border-primary custom-scrollbar resize-none outline-none"
                />
            </div>
        </div>
    )
}

function TunerSkeleton() {
    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm animate-pulse">
            <div className="h-7 w-48 bg-slate-200 rounded mb-8" />
            <div className="space-y-6">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="space-y-2">
                        <div className="h-4 w-24 bg-slate-200 rounded" />
                        <div className="h-2 w-full bg-slate-100 rounded-full" />
                    </div>
                ))}
            </div>
            <div className="border-t border-slate-100 mt-8 pt-6 space-y-4">
                <div className="h-4 w-36 bg-slate-200 rounded" />
                <div className="h-9 w-full bg-slate-100 rounded-lg" />
                <div className="h-36 w-full bg-slate-100 rounded-lg" />
            </div>
        </div>
    )
}
