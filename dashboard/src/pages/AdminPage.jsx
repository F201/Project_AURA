import { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabaseClient'
import AdminSidebar from '../components/AdminSidebar'
import StatusCards from '../components/StatusCards'
import PersonalityTuner from '../components/PersonalityTuner'
import KnowledgeBase from '../components/KnowledgeBase'
import SystemLogs from '../components/SystemLogs'
import ApiKeys from '../components/ApiKeys'

export default function AdminPage() {
    const [settings, setSettings] = useState(null)
    const [deployState, setDeployState] = useState('idle') // 'idle' | 'saving' | 'saved' | 'error'
    const pendingRef = useRef(null)

    useEffect(() => {
        loadSettings()
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

    const handleChange = (updated) => {
        pendingRef.current = updated
    }

    const deployChanges = async () => {
        if (!pendingRef.current) return
        setDeployState('saving')
        try {
            const patch = { ...pendingRef.current }
            delete patch.id
            delete patch.created_at
            patch.updated_at = new Date().toISOString()

            const { error } = await supabase
                .from('personality_settings')
                .update(patch)
                .eq('id', 1)

            if (error) throw error

            setSettings(pendingRef.current)
            setDeployState('saved')
            setTimeout(() => setDeployState('idle'), 2500)
        } catch (err) {
            console.error('Deploy failed:', err)
            setDeployState('error')
            setTimeout(() => setDeployState('idle'), 3000)
        }
    }

    const deployButtonProps = {
        idle:   { label: 'Deploy Changes', icon: 'bolt',           cls: 'bg-primary hover:bg-primary/90 shadow-primary/20' },
        saving: { label: 'Saving...',       icon: 'hourglass_top',  cls: 'bg-primary/70 cursor-not-allowed' },
        saved:  { label: 'Deployed!',       icon: 'check_circle',   cls: 'bg-emerald-500 shadow-emerald-200' },
        error:  { label: 'Failed',          icon: 'error',          cls: 'bg-red-500 shadow-red-200' },
    }[deployState]

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
                        <button
                            onClick={deployChanges}
                            disabled={deployState === 'saving'}
                            className={`${deployButtonProps.cls} text-white px-6 py-2 rounded-full font-bold transition-all shadow-lg flex items-center gap-2 cursor-pointer`}
                        >
                            <span className="material-icons-round text-sm">{deployButtonProps.icon}</span>
                            {deployButtonProps.label}
                        </button>
                    </div>
                </header>

                <StatusCards />

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                    <PersonalityTuner settings={settings} onChange={handleChange} />
                    <KnowledgeBase />
                </div>

                <div className="mb-8">
                    <ApiKeys />
                </div>

                <SystemLogs />
            </main>
        </div>
    )
}
