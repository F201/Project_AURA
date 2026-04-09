const SLIDERS = [
    { key: 'empathy',   label: 'Empathy' },
    { key: 'humor',     label: 'Humor' },
    { key: 'formality', label: 'Formality' },
]

const PROVIDERS = [
    { value: 'openrouter', label: 'OpenRouter',    hint: 'Routes to any model (DeepSeek, GPT, Mistral…)' },
    { value: 'openai',     label: 'OpenAI',         hint: 'Direct GPT-4o / o1 access' },
    { value: 'anthropic',  label: 'Anthropic',      hint: 'Claude 3.5 / Claude 4' },
    { value: 'groq',       label: 'Groq',           hint: 'Ultra-fast Llama / Mixtral inference' },
    { value: 'ollama',     label: 'Ollama (local)',  hint: 'Local models via Ollama' },
]

const MODEL_SUGGESTIONS = {
    openrouter: ['deepseek/deepseek-v3.2', 'openai/gpt-4o', 'anthropic/claude-sonnet-4-5', 'mistralai/mistral-nemo'],
    openai:     ['gpt-4o', 'gpt-4o-mini', 'o1-mini'],
    anthropic:  ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5-20251001'],
    groq:       ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
    ollama:     ['llama3.2', 'mistral', 'gemma2', 'qwen2.5'],
}

export default function PersonalityTuner({ settings, onChange }) {
    if (!settings) return <TunerSkeleton />

    const provider    = settings.provider || 'openrouter'
    const suggestions = MODEL_SUGGESTIONS[provider] || []
    const providerInfo = PROVIDERS.find(p => p.value === provider)

    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
            <h3 className="text-xl font-bold mb-8 flex items-center gap-2">
                <span className="material-icons-round text-primary">tune</span>
                Personality Tuner
            </h3>

            {/* Provider picker */}
            <div className="mb-6">
                <label className="block text-sm font-bold text-slate-500 uppercase tracking-widest mb-2">
                    LLM Provider
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {PROVIDERS.map(p => (
                        <button key={p.value} onClick={() => onChange({ provider: p.value })} title={p.hint}
                            className={`px-3 py-2 rounded-lg text-sm font-medium border transition-all text-left ${
                                provider === p.value
                                    ? 'bg-primary text-white border-primary shadow-sm'
                                    : 'bg-bg-light text-slate-600 border-slate-200 hover:border-primary/40'
                            }`}>
                            {p.label}
                        </button>
                    ))}
                </div>
                {providerInfo && (
                    <p className="text-xs text-slate-400 mt-1.5">{providerInfo.hint}</p>
                )}
            </div>

            {/* Model input */}
            <div className="mb-6">
                <label className="block text-sm font-bold text-slate-500 uppercase tracking-widest mb-2">
                    Model
                </label>
                <input
                    type="text"
                    value={settings.model || ''}
                    onChange={e => onChange({ model: e.target.value })}
                    placeholder="e.g. deepseek/deepseek-v3.2"
                    list="model-suggestions"
                    className="w-full bg-bg-light border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                />
                <datalist id="model-suggestions">
                    {suggestions.map(m => <option key={m} value={m} />)}
                </datalist>
                {suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                        {suggestions.map(m => (
                            <button key={m} onClick={() => onChange({ model: m })}
                                className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 hover:bg-primary/10 hover:text-primary transition-colors font-mono">
                                {m.split('/').pop()}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Temperature + Max Tokens */}
            <div className="grid grid-cols-2 gap-4 mb-8">
                <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">
                        Temperature&nbsp;<span className="text-primary font-bold">{settings.temperature ?? 0.8}</span>
                    </label>
                    <input type="range" min="0" max="1" step="0.05"
                        value={settings.temperature ?? 0.8}
                        onChange={e => onChange({ temperature: parseFloat(e.target.value) })}
                        className="w-full accent-primary"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">
                        Max Tokens&nbsp;<span className="text-primary font-bold">{settings.max_tokens ?? 300}</span>
                    </label>
                    <input type="range" min="100" max="1000" step="50"
                        value={settings.max_tokens ?? 300}
                        onChange={e => onChange({ max_tokens: parseInt(e.target.value) })}
                        className="w-full accent-primary"
                    />
                </div>
            </div>

            {/* Personality sliders */}
            <div className="space-y-6">
                {SLIDERS.map(({ key, label }) => (
                    <div key={key} className="space-y-2">
                        <div className="flex justify-between text-sm font-medium">
                            <label className="text-slate-500">{label}</label>
                            <span className="text-primary">{settings[key]}%</span>
                        </div>
                        <input type="range" min="0" max="100"
                            value={settings[key]}
                            onChange={e => onChange({ [key]: parseInt(e.target.value) })}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-primary"
                        />
                    </div>
                ))}
            </div>

            {/* System prompt */}
            <div className="mt-8">
                <label className="block text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">
                    System Prompt Override
                </label>
                <textarea
                    value={settings.system_prompt || ''}
                    onChange={e => onChange({ system_prompt: e.target.value })}
                    placeholder="Enter core instructions here..."
                    className="w-full h-32 bg-bg-light border border-slate-200 rounded-lg p-4 font-mono text-sm focus:ring-primary focus:border-primary custom-scrollbar resize-none outline-none"
                />
            </div>
        </div>
    )
}

function TunerSkeleton() {
    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm animate-pulse">
            <div className="h-7 w-48 bg-slate-200 rounded mb-8" />
            <div className="space-y-4 mb-8">
                <div className="h-4 w-24 bg-slate-200 rounded" />
                <div className="grid grid-cols-3 gap-2">
                    {[1,2,3].map(i => <div key={i} className="h-9 bg-slate-100 rounded-lg" />)}
                </div>
                <div className="h-9 w-full bg-slate-100 rounded-lg" />
            </div>
            <div className="space-y-6">
                {[1,2,3].map(i => (
                    <div key={i} className="space-y-2">
                        <div className="h-4 w-24 bg-slate-200 rounded" />
                        <div className="h-2 w-full bg-slate-100 rounded-full" />
                    </div>
                ))}
            </div>
        </div>
    )
}
