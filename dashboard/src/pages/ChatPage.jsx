import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import Sidebar from '../components/Sidebar'
import ChatHeader from '../components/ChatHeader'
import ChatFeed from '../components/ChatFeed'
import ChatInput from '../components/ChatInput'
import { Presence } from '../components/Presence'
import CallOverlay from '../components/CallOverlay'
import SlideOver from '../components/SlideOver'
import PersonalityTuner from '../components/PersonalityTuner'
import KnowledgeBase from '../components/KnowledgeBase'
import StatusCards from '../components/StatusCards'
import SystemLogs from '../components/SystemLogs'
import { getOrCreateIdentity } from '../lib/user'

const AI_SERVICE = `http://${window.location.hostname}:8000/api/v1`

export default function ChatPage() {
    const [conversations, setConversations] = useState([])
    const [activeConvoId, setActiveConvoId] = useState(null)
    const [messages, setMessages] = useState([])
    const [isCallActive, setIsCallActive] = useState(false)
    const [isAdminOpen, setIsAdminOpen] = useState(false)
    const [settings, setSettings] = useState(null)
    const [isSending, setIsSending] = useState(false)
    const feedRef = useRef(null)
    const presenceRef = useRef(null)
    const navigate = useNavigate()

    // ─── Load data on mount ────────────────
    useEffect(() => {
        loadConversations()
        loadSettings()
    }, [])

    // ─── Load messages when active conversation changes ──
    useEffect(() => {
        if (activeConvoId) loadMessages(activeConvoId)
        else setMessages([])
    }, [activeConvoId])

    // ─── Auto-scroll on new messages ────────────────
    useEffect(() => {
        if (feedRef.current) {
            feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
        }
    }, [messages])

    // ─── Data fetching ──────────────────────────────
    const loadConversations = async () => {
        const { data } = await supabase
            .from('conversations')
            .select('*')
            .order('updated_at', { ascending: false })
        if (data) setConversations(data)
    }

    const loadMessages = async (convoId) => {
        // If we are currently sending a message to this conversation, avoid overwriting
        // the optimistic local state with a stale DB fetch (which might not have the new msg yet).
        if (isSending && activeConvoId === convoId) {
            console.log('[AURA] Skipping loadMessages during sending to prevent UI flicker');
            return;
        }

        const { data } = await supabase
            .from('messages')
            .select('*')
            .eq('conversation_id', convoId)
            .order('created_at', { ascending: true })

        // If we switched away while loading, don't update
        setActiveConvoId(current => {
            if (current === convoId && data) {
                setMessages(data)
            }
            return current
        })
    }

    const loadSettings = async () => {
        const { data } = await supabase.from('personality_settings').select('*').eq('id', 1).single()
        if (data) setSettings(data)
    }

    const updateSettings = async (patch) => {
        const updated = { ...settings, ...patch, updated_at: new Date().toISOString() }
        setSettings(updated)
        await supabase.from('personality_settings').update(patch).eq('id', 1)
    }

    // ─── New chat ───────────────────────────────────
    const handleNewChat = async () => {
        const { data } = await supabase
            .from('conversations')
            .insert({ title: 'New Chat' })
            .select()
            .single()
        if (data) {
            setConversations((prev) => [data, ...prev])
            setActiveConvoId(data.id)
        }
    }

    const isSendingRef = useRef(false)

    // ─── Send message ──────────────────────────────
    const handleSend = useCallback(async (text) => {
        if (isSendingRef.current) return

        isSendingRef.current = true
        setIsSending(true)

        let convoId = activeConvoId
        if (!convoId) {
            const { data } = await supabase
                .from('conversations')
                .insert({ title: text.slice(0, 50) })
                .select()
                .single()
            if (!data) {
                isSendingRef.current = false
                setIsSending(false)
                return
            }
            convoId = data.id
            setActiveConvoId(convoId)
            setConversations((prev) => [data, ...prev])
        }

        const tempUserMsg = { id: `temp-${Date.now()}`, role: 'user', content: text, conversation_id: convoId }
        setMessages((prev) => [...prev, tempUserMsg])

        const identity = getOrCreateIdentity()
        setIsSending(true)
        try {
            const res = await fetch(`${AI_SERVICE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, conversation_id: convoId, identity, stream: true }),
            })

            if (!res.ok) throw new Error(`API error: ${res.status}`)

            // Placeholder for AI message
            const aiMsgId = `temp-ai-${Date.now()}`
            setMessages((prev) => [...prev, {
                id: aiMsgId,
                role: 'aura',
                content: '',
                emotion: 'neutral',
                conversation_id: convoId,
            }])

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let fullText = ''
            let lastEmotion = 'neutral'

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value)
                const lines = chunk.split('\n')

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6))
                            if (data.text) {
                                fullText += data.text

                                // Scrub residual [emotion] tags using a global regex for clean UI
                                const scrubbedText = fullText.replace(/\[.*?\]/g, '').trim()

                                setMessages(prev => prev.map(m =>
                                    m.id === aiMsgId ? { ...m, content: scrubbedText } : m
                                ))
                            }
                            if (data.emotion) {
                                lastEmotion = data.emotion
                                setMessages(prev => prev.map(m =>
                                    m.id === aiMsgId ? { ...m, emotion: lastEmotion } : m
                                ))
                            }
                        } catch (e) {
                            // Partial JSON or heartbeat
                        }
                    }
                }
            }

            // Sync with DB after stream ends to ensure backend has persisted the full interaction
            setTimeout(() => loadMessages(convoId), 500)

            // If it was the first message, update the title
            if (convoId === activeConvoId && messages.length <= 1) {
                await supabase
                    .from('conversations')
                    .update({ title: text.slice(0, 50), updated_at: new Date().toISOString() })
                    .eq('id', convoId)
                loadConversations()
            }
        } catch (err) {
            console.error('[AURA] Chat error:', err)
            setMessages((prev) => [...prev, {
                id: `temp-err-${Date.now()}`,
                role: 'aura',
                content: "Hmm, my connection to the other side seems shaky right now~ Try again?",
                emotion: 'dizzy',
            }])
        } finally {
            isSendingRef.current = false
            setIsSending(false)
        }
    }, [activeConvoId, AI_SERVICE, loadConversations, loadMessages])

    return (
        <div className="flex h-screen overflow-hidden bg-bg-light text-slate-900 font-sans selection:bg-primary/20">

            {/* Sidebar (Left) */}
            <div className="w-[var(--sidebar-w)] shrink-0 border-r border-slate-700/50 bg-slate-900 z-20">
                <Sidebar
                    conversations={conversations}
                    activeId={activeConvoId}
                    onSelect={setActiveConvoId}
                    onNewChat={handleNewChat}
                />
            </div>

            {/* Main Interactive Region */}
            <main className="flex-1 flex flex-col relative overflow-hidden">
                <ChatHeader
                    onCallStart={() => setIsCallActive(true)}
                    isCallActive={isCallActive}
                    onTuningOpen={() => navigate('/admin')}
                />

                <div ref={feedRef} className="flex-1 overflow-y-auto px-6 py-8 custom-scrollbar">
                    <div className="max-w-3xl mx-auto w-full">
                        <ChatFeed messages={messages} />
                    </div>
                </div>

                <div className="p-6 bg-white border-t border-slate-100">
                    <div className="max-w-3xl mx-auto w-full">
                        <ChatInput onSend={handleSend} disabled={isSending} />
                    </div>
                </div>
            </main>

            {/* Immersive Interaction Layer (Old UI Revert) */}
            {isCallActive && (
                <CallOverlay
                    onClose={() => setIsCallActive(false)}
                    conversationId={activeConvoId}
                />
            )}
        </div>
    )
}
