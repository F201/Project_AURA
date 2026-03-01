import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'
import AdminSidebar from '../components/AdminSidebar'
import StatusCards from '../components/StatusCards'
import PersonalityTuner from '../components/PersonalityTuner'
import KnowledgeBase from '../components/KnowledgeBase'
import SystemLogs from '../components/SystemLogs'

export default function AdminPage() {
    const [settings, setSettings] = useState(null)

    useEffect(() => {
        loadSettings()
    }, [])

    const loadSettings = async () => {
        const { data } = await supabase
            .from('personality_settings')
            .select('*')
            .eq('id', 1)
            .single()
        if (data) setSettings(data)
    }

    const updateSettings = async (patch) => {
        const updated = { ...settings, ...patch, updated_at: new Date().toISOString() }
        setSettings(updated)
        await supabase.from('personality_settings').update(patch).eq('id', 1)
    }

    return (
        <div className="flex h-screen overflow-hidden bg-bg-light text-slate-800 font-admin">
            <AdminSidebar />

            <main className="flex-1 p-6 lg:p-10 overflow-y-auto custom-scrollbar">
                {/* Header */}
                <header className="mb-10 flex justify-between items-end">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight mb-1">System Control Center</h1>
                        <p className="text-slate-500 font-medium">AURA AI • Instance Node #772-Beta</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-full border border-slate-200">
                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-sm font-semibold">Live Connection</span>
                        </div>
                        <button className="bg-primary hover:bg-primary/90 text-white px-6 py-2 rounded-full font-bold transition-all shadow-lg shadow-primary/20 flex items-center gap-2 cursor-pointer">
                            <span className="material-icons-round text-sm">bolt</span>
                            Deploy Changes
                        </button>
                    </div>
                </header>

                <StatusCards />

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                    <PersonalityTuner settings={settings} onUpdate={updateSettings} />
                    <KnowledgeBase />
                </div>

                <SystemLogs />
            </main>
        </div>
    )
}
