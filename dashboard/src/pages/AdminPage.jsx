import { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabaseClient'
import AdminSidebar from '../components/AdminSidebar'
import StatusCards from '../components/StatusCards'
import PersonalityTuner from '../components/PersonalityTuner'
import ApiKeys from '../components/ApiKeys'
import KnowledgeBase from '../components/KnowledgeBase'
import SystemLogs from '../components/SystemLogs'

const AI_SERVICE = `http://${window.location.hostname}:8000/api/v1`

export default function AdminPage() {
    const [settings, setSettings] = useState(null)
    const [apiKeys, setApiKeys] = useState(null)
    const [saving, setSaving] = useState(false)
    const [saveMsg, setSaveMsg] = useState('')
    const pendingRef = useRef({})

    useEffect(() => {
        loadSettings()
        loadApiKeys()
    }, [])

    const loadSettings = async () => {
        const { data } = await supabase
            .from('personality_settings')
            .select('*')
            .eq('id', 1)
            .single()
        if (data) {
            setSettings(data)
            pendingRef.current = data
        }
    }

    const loadApiKeys = async () => {
        try {
            const res = await fetch(`${AI_SERVICE}/settings/keys`)
            const data = await res.json()
            if (data) setApiKeys(data)
        } catch (err) {
            console.error('Failed to load API key status:', err)
        }
    }

    const handleSettingsChange = (patch) => {
        const updated = { ...settings, ...patch }
        setSettings(updated)
        pendingRef.current = { ...pendingRef.current, ...patch }
    }

    const handleDeploy = async () => {
        setSaving(true)
        setSaveMsg('')
        try {
            const patch = pendingRef.current
            if (Object.keys(patch).length > 0) {
                await supabase
                    .from('personality_settings')
                    .update({ ...patch, updated_at: new Date().toISOString() })
                    .eq('id', 1)

                // Also push to AI service API
                await fetch(`${AI_SERVICE}/settings`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patch),
                })
            }
            pendingRef.current = {}
            setSaveMsg('Settings deployed successfully!')
            setTimeout(() => setSaveMsg(''), 3000)
        } catch (err) {
            console.error('Deploy error:', err)
            setSaveMsg('Deploy failed. Check console.')
        } finally {
            setSaving(false)
        }
    }

    const hasPendingChanges = Object.keys(pendingRef.current).length > 0

    return (
        <div className="flex h-screen overflow-hidden bg-bg-light text-slate-800 font-admin">
            <AdminSidebar />

            <main className="flex-1 p-6 lg:p-10 overflow-y-auto custom-scrollbar">
                {/* Header */}
                <header className="mb-10 flex justify-between items-end">
                    <div>
                        <h1 className="text-4xl font-black tracking-tight text-slate-800 mb-2">Project AURA <span className="text-slate-400 font-light">System Control Center</span></h1>
                        <p className="text-slate-500 font-medium">Project AURA • Instance Node #772-Beta</p>
                    </div>
                    <div className="flex items-center gap-4">
                        {saveMsg && (
                            <span className={`text-sm font-semibold ${saveMsg.includes('success') ? 'text-emerald-600' : 'text-red-500'}`}>
                                {saveMsg}
                            </span>
                        )}
                        <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-full border border-slate-200">
                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-sm font-semibold">Live Connection</span>
                        </div>
                        <button
                            onClick={handleDeploy}
                            disabled={saving}
                            className="bg-primary hover:bg-primary/90 disabled:opacity-50 text-white px-6 py-2 rounded-full font-bold transition-all shadow-lg shadow-primary/20 flex items-center gap-2 cursor-pointer"
                        >
                            <span className="material-icons-round text-sm">{saving ? 'hourglass_top' : 'bolt'}</span>
                            {saving ? 'Deploying...' : 'Deploy Changes'}
                        </button>
                    </div>
                </header>

                <StatusCards />

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                    <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm">
                        <h2 className="text-lg font-black text-slate-800 mb-6 flex items-center gap-2">
                            <span className="material-icons-round text-primary text-xl">psychology</span>
                            Personality Engine
                        </h2>
                        <PersonalityTuner settings={settings} onChange={handleSettingsChange} />
                    </div>
                    <div className="flex flex-col gap-8">
                        <ApiKeys />
                        <KnowledgeBase />
                    </div>
                </div>

                <SystemLogs />
            </main>
        </div>
    )
}
