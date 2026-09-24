import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient' // Sesuaikan path ini dengan project kamu

const SLIDERS = [
    { key: 'empathy', label: 'Empathy' },
    { key: 'humor', label: 'Humor' },
    { key: 'formality', label: 'Formality' },
]

const PROVIDERS = [
    { value: 'openrouter', label: 'OpenRouter', hint: 'Routes to any model (DeepSeek, GPT, Mistral…)' },
    { value: 'openai', label: 'OpenAI', hint: 'Direct GPT-4o / o1 access' },
    { value: 'anthropic', label: 'Anthropic', hint: 'Claude 3.5 / Claude 4' },
    { value: 'groq', label: 'Groq', hint: 'Ultra-fast Llama / Mixtral inference' },
    { value: 'ollama', label: 'Ollama (local)', hint: 'Local models via Ollama' },
]

const MODEL_SUGGESTIONS = {
    openrouter: ['deepseek/deepseek-v4-flash', 'deepseek/deepseek-v3.2', 'openai/gpt-4o', 'anthropic/claude-sonnet-4-5', 'mistralai/mistral-nemo'],
    openai: ['gpt-5.5', 'gpt-5.4', 'gpt-5.3'],
    anthropic: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5-20251001'],
    groq: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
    ollama: ['llama3.2', 'mistral', 'gemma2', 'qwen2.5'],
}

export default function PersonalityTuner() {
    // 1. Inisialisasi State
    const [settings, setSettings] = useState({
        provider: 'openrouter', model: '', temperature: 0.8, max_tokens: 300,
        empathy: 50, humor: 50, formality: 50, system_prompt: ''
    })
    const [saveState, setSaveState] = useState('idle')
    const [loaded, setLoaded] = useState(false)

    // 2. READ: Ambil data dari Supabase saat komponen dimuat
    useEffect(() => {
        supabase.from('personality_settings').select('*').eq('id', 1).single()
            .then(({ data, error }) => {
                if (data) {
                    setSettings(prev => ({ ...prev, ...data }))
                }
                setLoaded(true)
            })
    }, [])

    // Fungsi untuk mengubah state lokal
    const handleChange = (updates) => {
        setSettings(prev => ({ ...prev, ...updates }))
    }

    // 3. UPDATE: Simpan data ke Supabase
    const saveSettings = async () => {
        setSaveState('saving')
        try {
            // Siapkan data yang mau dikirim (pastikan kolom ini ada di database!)
            const payload = {
                empathy: settings.empathy,
                humor: settings.humor,
                formality: settings.formality,
                system_prompt: settings.system_prompt,
                // Kalau error, hapus/comment 4 baris di bawah ini sampai kamu nambahin kolomnya di DB
                provider: settings.provider,
                model: settings.model,
                temperature: settings.temperature,
                max_tokens: settings.max_tokens,
                updated_at: new Date().toISOString()
            }

            const { error } = await supabase.from('personality_settings').update(payload).eq('id', 1)
            
            if (error) throw error
            setSaveState('saved')
            setTimeout(() => setSaveState('idle'), 2500)
        } catch (err) {
            console.error('Failed to save personality settings:', err)
            setSaveState('error')
            setTimeout(() => setSaveState('idle'), 3000)
        }
    }

    // Tampilan dinamis tombol save
    const btn = {
        idle: { label: 'Save Settings', icon: 'settings', cls: 'bg-[#f97316] hover:bg-[#ea580c] shadow-orange-500/20' },
        saving: { label: 'Saving...', icon: 'hourglass_top', cls: 'bg-orange-400 cursor-not-allowed' },
        saved: { label: 'Saved!', icon: 'check_circle', cls: 'bg-emerald-500 shadow-emerald-200' },
        error: { label: 'Failed', icon: 'error', cls: 'bg-red-500 shadow-red-200' },
    }[saveState]

    if (!loaded) return <TunerSkeleton />

    const provider = settings.provider || 'openrouter'
    const suggestions = MODEL_SUGGESTIONS[provider] || []

    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm flex flex-col gap-8">
            
            {/* HEADER: Judul & Tombol Save (Sama persis kayak API Keys) */}
            <div className="flex items-center justify-between">
                <h3 className="text-xl font-bold flex items-center gap-2">
                    <span className="material-icons-round text-[#f97316]">psychology</span>
                    Personality Engine
                </h3>
                <button
                    onClick={saveSettings}
                    disabled={saveState === 'saving' || !loaded}
                    className={`${btn.cls} text-white px-5 py-2 rounded-full text-sm font-bold transition-all shadow-lg flex items-center gap-2`}
                >
                    <span className="material-icons-round text-sm">{btn.icon}</span>
                    {btn.label}
                </button>
            </div>

            {/* Provider picker */}
            <div className="space-y-4">
                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                    LLM PROVIDER
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {PROVIDERS.map(p => (
                        <button key={p.value} onClick={() => handleChange({ provider: p.value })} title={p.hint}
                            className={`px-4 py-3 rounded-2xl text-xs font-bold border transition-all text-left group cursor-pointer ${provider === p.value
                                ? 'bg-[#f97316] text-white border-[#f97316] shadow-lg shadow-orange-500/20'
                                : 'bg-white text-slate-500 border-slate-200 hover:border-orange-500/30 hover:text-[#f97316]'
                                }`}>
                            <div className="flex flex-col gap-0.5">
                                <span>{p.label}</span>
                                <span className={`text-[9px] font-medium opacity-50 ${provider === p.value ? 'text-white' : ''} truncate`}>
                                    {p.hint.split('(')[0]}
                                </span>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Model selection */}
            <div className="space-y-4">
                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                    MODEL ARCHITECTURE
                </label>
                <div className="relative group">
                    <input
                        type="text"
                        value={settings.model || ''}
                        onChange={e => handleChange({ model: e.target.value })}
                        placeholder="e.g. deepseek/deepseek-v3.2"
                        list="model-suggestions"
                        className="w-full bg-white border border-slate-200 rounded-2xl px-5 py-4 text-sm font-mono text-slate-800 placeholder-slate-300 focus:border-[#f97316] focus:ring-4 focus:ring-orange-500/10 outline-none transition-all"
                    />
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 group-focus-within:text-[#f97316] transition-all">
                        <span className="material-icons-round text-sm">precision_manufacturing</span>
                    </div>
                </div>
                <datalist id="model-suggestions">
                    {suggestions.map(m => <option key={m} value={m} />)}
                </datalist>
                {suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                        {suggestions.map(m => (
                            <button key={m} onClick={() => handleChange({ model: m })}
                                className="text-[10px] px-3 py-1.5 rounded-full bg-slate-100 text-slate-500 hover:bg-orange-500/10 hover:text-[#f97316] transition-all font-bold border border-transparent cursor-pointer">
                                {m.split('/').pop()}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Hyperparameters */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                <div className="space-y-4">
                    <div className="flex justify-between items-center">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Creativity</label>
                        <span className="text-[#f97316] font-mono text-xs font-bold px-2 py-0.5 bg-orange-500/10 rounded">{settings.temperature ?? 0.8}</span>
                    </div>
                    <input type="range" min="0" max="1" step="0.05"
                        value={settings.temperature ?? 0.8}
                        onChange={e => handleChange({ temperature: parseFloat(e.target.value) })}
                        className="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-[#f97316]"
                    />
                </div>
                <div className="space-y-4">
                    <div className="flex justify-between items-center">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Response Depth</label>
                        <span className="text-[#f97316] font-mono text-xs font-bold px-2 py-0.5 bg-orange-500/10 rounded">{settings.max_tokens ?? 300}t</span>
                    </div>
                    <input type="range" min="100" max="1000" step="50"
                        value={settings.max_tokens ?? 300}
                        onChange={e => handleChange({ max_tokens: parseInt(e.target.value) })}
                        className="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-[#f97316]"
                    />
                </div>
            </div>

            {/* Personality Sliders */}
            <div className="space-y-8 bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                {SLIDERS.map(({ key, label }) => (
                    <div key={key} className="space-y-3">
                        <div className="flex justify-between items-center">
                            <label className="text-[11px] font-bold text-slate-500 tracking-wider capitalize">{label}</label>
                            <span className="text-[#f97316] font-black text-xs">{settings[key]}%</span>
                        </div>
                        <div className="relative flex items-center h-2">
                            <div className="absolute inset-x-0 h-1.5 bg-slate-100 rounded-full" />
                            <div className="absolute h-1.5 bg-[#f97316] rounded-full" style={{ width: `${settings[key]}%` }} />
                            <input type="range" min="0" max="100"
                                value={settings[key]}
                                onChange={e => handleChange({ [key]: parseInt(e.target.value) })}
                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                            />
                            <div className="absolute w-4 h-4 bg-white rounded-full shadow-md border-2 border-[#f97316] pointer-events-none" style={{ left: `calc(${settings[key]}% - 8px)` }} />
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={settings[key]}
                            onChange={(e) => onUpdate({ [key]: parseInt(e.target.value) })}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer slider-thumb accent-primary"
                        />
                    </div>
                ))}
            </div>

            <div className="mt-10">
                <label className="block text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">
                    System Prompt Override
                </label>
                <div className="relative group">
                    <textarea
                        value={settings.system_prompt || ''}
                        onChange={e => handleChange({ system_prompt: e.target.value })}
                        placeholder="Define AURA's fundamental behavior..."
                        className="w-full h-40 bg-white border border-slate-200 rounded-2xl p-5 font-mono text-sm text-slate-800 placeholder-slate-300 focus:border-[#f97316] outline-none transition-all focus:ring-4 focus:ring-orange-500/10 resize-none custom-scrollbar"
                    />
                    <div className="absolute right-4 bottom-4 text-slate-200 group-focus-within:text-[#f97316] transition-colors">
                        <span className="material-icons-round text-3xl">psychology</span>
                    </div>
                </div>
            </div>
        </div>
    )
}

function TunerSkeleton() {
    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm animate-pulse">
            <div className="h-7 w-48 bg-slate-200 rounded mb-8" />
            <div className="space-y-8">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="space-y-3">
                        <div className="h-4 w-24 bg-slate-200 rounded" />
                        <div className="h-2 w-full bg-slate-100 rounded-full" />
                    </div>
                ))}
            </div>
            <div className="mt-10">
                <div className="h-4 w-36 bg-slate-200 rounded mb-3" />
                <div className="h-32 w-full bg-slate-100 rounded-lg" />
            </div>
        </div>
    )
}