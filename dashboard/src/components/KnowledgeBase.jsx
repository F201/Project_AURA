import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'

export default function KnowledgeBase() {
    const [files, setFiles] = useState([])
    const [uploading, setUploading] = useState(false)

    useEffect(() => { loadFiles() }, [])

    const loadFiles = async () => {
        const { data } = await supabase
            .from('knowledge_base')
            .select('*')
            .order('created_at', { ascending: false })
        if (data) setFiles(data)
    }

    const handleUpload = async (e) => {
        const file = e.target.files?.[0]
        if (!file) return

        setUploading(true)
        try {
            // Upload to Supabase Storage
            const path = `knowledge/${Date.now()}_${file.name}`
            const { error: uploadErr } = await supabase.storage
                .from('knowledge')
                .upload(path, file)

            if (uploadErr) {
                // If bucket doesn't exist, just save metadata
                console.warn('[AURA] Storage upload skipped:', uploadErr.message)
            }

            // Save metadata
            const { data } = await supabase
                .from('knowledge_base')
                .insert({
                    filename: file.name,
                    size_bytes: file.size,
                    mime_type: file.type || 'application/octet-stream',
                    storage_path: path,
                })
                .select()
                .single()

            if (data) setFiles((prev) => [data, ...prev])

            // Also send to local RAG backend
            try {
                const formData = new FormData()
                formData.append('file', file)
                await fetch('http://localhost:8000/api/v1/rag/upload', {
                    method: 'POST',
                    body: formData
                })
            } catch (backendErr) {
                console.warn('[AURA] Failed to send to local RAG backend:', backendErr)
            }
        } catch (err) {
            console.error('[AURA] Upload failed:', err)
        } finally {
            setUploading(false)
            e.target.value = '' // Reset file input
        }
    }

    const handleDelete = async (id) => {
        await supabase.from('knowledge_base').delete().eq('id', id)
        setFiles((prev) => prev.filter((f) => f.id !== id))
    }

    const mimeIcon = (mime) => {
        if (mime?.includes('pdf')) return 'description'
        if (mime?.includes('zip') || mime?.includes('compressed')) return 'folder_zip'
        if (mime?.includes('csv') || mime?.includes('spreadsheet')) return 'table_chart'
        return 'insert_drive_file'
    }

    const formatSize = (bytes) => {
        if (!bytes) return '0 B'
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
        <div className="flex flex-col h-full">
            <div className="flex justify-between items-end mb-8 px-2">
                <div className="space-y-1">
                    <h3 className="text-xl font-black text-white tracking-widest uppercase flex items-center gap-3">
                        <span className="w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_#ff7e33]" />
                        Cognitive Core
                    </h3>
                    <p className="text-[10px] text-white/20 font-black uppercase tracking-[0.2em]">Contextual Data Vectors</p>
                </div>
                <div className="px-3 py-1 bg-white/5 rounded-full border border-white/5 shadow-inner">
                    <span className="text-[10px] font-black text-primary/80 uppercase tracking-tighter">{files.length} ASSETS MAPPED</span>
                </div>
            </div>

            {/* File list */}
            <div className="flex-1 space-y-3 mb-10 overflow-y-auto max-h-72 custom-scrollbar-dark pr-3">
                {files.map((f) => (
                    <div key={f.id} className="flex items-center justify-between p-4 bg-white/[0.03] rounded-2xl group border border-white/5 hover:border-primary/20 hover:bg-white/5 transition-all shadow-lg">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 bg-black/40 rounded-xl flex items-center justify-center text-primary border border-white/5 shadow-inner group-hover:scale-110 transition-transform">
                                <span className="material-icons-round text-xl">{mimeIcon(f.mime_type)}</span>
                            </div>
                            <div>
                                <h4 className="text-[13px] font-bold text-white/90 group-hover:text-primary transition-colors">{f.filename}</h4>
                                <div className="flex items-center gap-2 mt-1">
                                    <span className="text-[9px] text-white/20 font-black uppercase tracking-widest">{formatSize(f.size_bytes)}</span>
                                    <span className="w-1 h-1 rounded-full bg-white/10" />
                                    <span className="text-[9px] text-white/20 font-black uppercase tracking-widest">{new Date(f.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => handleDelete(f.id)}
                            className="w-8 h-8 flex items-center justify-center rounded-lg text-white/20 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
                        >
                            <span className="material-icons-round text-lg">delete_sweep</span>
                        </button>
                    </div>
                ))}

                {files.length === 0 && (
                    <div className="py-12 flex flex-col items-center justify-center opacity-10 grayscale">
                        <span className="material-icons-round text-6xl mb-4">folder_off</span>
                        <p className="text-xs font-black uppercase tracking-[0.3em]">No Data Mapped</p>
                    </div>
                )}
            </div>

            {/* Upload zone */}
            <label className="relative overflow-hidden border-2 border-dashed border-white/5 rounded-3xl p-10 flex flex-col items-center justify-center text-center group hover:border-primary/30 hover:bg-primary/[0.02] transition-all cursor-pointer bg-black/20 shadow-inner">
                <div className="absolute inset-0 aura-gradient opacity-0 group-hover:opacity-[0.03] transition-opacity pointer-events-none" />
                <input type="file" onChange={handleUpload} className="hidden" accept=".pdf,.txt,.json,.csv,.zip,.pptx" />

                <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-5 group-hover:scale-110 group-hover:bg-primary/10 transition-all shadow-xl border border-white/5 group-hover:border-primary/20">
                    <span className={`material-icons-round text-3xl transition-all ${uploading ? 'text-primary animate-spin' : 'text-white/40 group-hover:text-primary'}`}>
                        {uploading ? 'hourglass_empty' : 'auto_mode'}
                    </span>
                </div>

                <div className="space-y-1">
                    <p className="font-black text-xs text-white/80 group-hover:text-white uppercase tracking-[0.1em] transition-colors">
                        {uploading ? 'INGESTING DATA...' : 'INITIATE NEURAL INGESTION'}
                    </p>
                    <p className="text-[10px] text-white/20 font-medium tracking-tight">
                        Drop PDF, TXT, JSON, or CSV (UP TO 50MB)
                    </p>
                </div>
            </label>
        </div>
    )
}
