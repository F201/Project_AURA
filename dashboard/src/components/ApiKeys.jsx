import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'

const KEY_GROUPS = [
    {
        label: 'LLM Provider',
        icon: 'psychology',
        fields: [
            { key: 'openrouter_api_key', label: 'OpenRouter API Key', placeholder: 'sk-or-v1-...' },
        ],
    },
    {
        label: 'Voice',
        icon: 'mic',
        fields: [
            { key: 'deepgram_api_key', label: 'Deepgram API Key (STT)', placeholder: 'your_deepgram_key' },
            { key: 'cartesia_api_key', label: 'Cartesia API Key (TTS)', placeholder: 'your_cartesia_key', note: 'Requires agent restart to apply' },
        ],
    },
    {
        label: 'LiveKit',
        icon: 'cell_tower',
        note: 'Changes require agent restart',
        fields: [
            { key: 'livekit_url', label: 'LiveKit URL', placeholder: 'wss://your-project.livekit.cloud' },
            { key: 'livekit_api_key', label: 'LiveKit API Key', placeholder: 'API key' },
            { key: 'livekit_api_secret', label: 'LiveKit API Secret', placeholder: 'API secret' },
        ],
    },
]

export default function ApiKeys() {
    const [draft, setDraft] = useState({})
    const [visible, setVisible] = useState({})
    const [saveState, setSaveState] = useState('idle') // 'idle' | 'saving' | 'saved' | 'error'
    const [loaded, setLoaded] = useState(false)

    useEffect(() => {
        supabase
            .from('api_keys')
            .select('*')
            .eq('id', 1)
            .single()
            .then(({ data }) => {
                if (data) setDraft(data)
                setLoaded(true)
            })
    }, [])

    const patch = (key, value) => setDraft((d) => ({ ...d, [key]: value }))

    const toggleVisible = (key) => setVisible((v) => ({ ...v, [key]: !v[key] }))

    const saveKeys = async () => {
        setSaveState('saving')
        try {
            const payload = { ...draft }
            delete payload.id
            payload.updated_at = new Date().toISOString()

            const { error } = await supabase
                .from('api_keys')
                .update(payload)
                .eq('id', 1)

            if (error) throw error
            setSaveState('saved')
            setTimeout(() => setSaveState('idle'), 2500)
        } catch (err) {
            console.error('Failed to save API keys:', err)
            setSaveState('error')
            setTimeout(() => setSaveState('idle'), 3000)
        }
    }

    const btnProps = {
        idle:   { label: 'Save API Keys',  icon: 'key',           cls: 'bg-primary hover:bg-primary/90 shadow-primary/20' },
        saving: { label: 'Saving...',       icon: 'hourglass_top', cls: 'bg-primary/70 cursor-not-allowed' },
        saved:  { label: 'Keys Saved!',     icon: 'check_circle',  cls: 'bg-emerald-500 shadow-emerald-200' },
        error:  { label: 'Save Failed',     icon: 'error',         cls: 'bg-red-500 shadow-red-200' },
    }[saveState]

    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-8">
                <h3 className="text-xl font-bold flex items-center gap-2">
                    <span className="material-icons-round text-primary">vpn_key</span>
                    API Keys
                </h3>
                <button
                    onClick={saveKeys}
                    disabled={saveState === 'saving' || !loaded}
                    className={`${btnProps.cls} text-white px-5 py-2 rounded-full text-sm font-bold transition-all shadow-lg flex items-center gap-2`}
                >
                    <span className="material-icons-round text-sm">{btnProps.icon}</span>
                    {btnProps.label}
                </button>
            </div>

            <div className="space-y-8">
                {KEY_GROUPS.map(({ label, icon, note, fields }) => (
                    <div key={label}>
                        <div className="flex items-center gap-2 mb-3">
                            <span className="material-icons-round text-base text-slate-400">{icon}</span>
                            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{label}</span>
                            {note && (
                                <span className="ml-auto text-xs text-amber-500 font-medium flex items-center gap-1">
                                    <span className="material-icons-round text-xs">info</span>
                                    {note}
                                </span>
                            )}
                        </div>
                        <div className="space-y-3">
                            {fields.map(({ key, label: fieldLabel, placeholder, note: fieldNote }) => (
                                <div key={key}>
                                    <label className="block text-sm font-medium text-slate-500 mb-1">{fieldLabel}</label>
                                    <div className="relative">
                                        <input
                                            type={visible[key] ? 'text' : 'password'}
                                            value={draft[key] ?? ''}
                                            onChange={(e) => patch(key, e.target.value)}
                                            placeholder={loaded ? placeholder : '••••••••'}
                                            className="w-full bg-bg-light border border-slate-200 rounded-lg px-3 py-2 pr-10 text-sm font-mono focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => toggleVisible(key)}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                                        >
                                            <span className="material-icons-round text-base">
                                                {visible[key] ? 'visibility_off' : 'visibility'}
                                            </span>
                                        </button>
                                    </div>
                                    {fieldNote && (
                                        <p className="text-xs text-amber-500 mt-1 flex items-center gap-1">
                                            <span className="material-icons-round text-xs">info</span>
                                            {fieldNote}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <p className="mt-6 text-xs text-slate-400 flex items-start gap-1.5">
                <span className="material-icons-round text-xs mt-0.5">lock</span>
                Keys are stored in your private Supabase database. Leave a field empty to use the value from the server's <code className="font-mono">.env</code> file.
            </p>
        </div>
    )
}
