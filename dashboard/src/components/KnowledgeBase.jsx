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
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm flex flex-col">
            <div className="flex justify-between items-center mb-8">
                <h3 className="text-xl font-bold flex items-center gap-2">
                    <span className="material-icons-round text-primary">auto_stories</span>
                    Knowledge Base
                </h3>
                <span className="text-sm font-bold text-slate-400">{files.length} files</span>
            </div>

            {/* File list */}
            <div className="flex-1 space-y-4 mb-8 overflow-y-auto max-h-64 custom-scrollbar pr-2">
                {files.map((f) => (
                    <div key={f.id} className="flex items-center justify-between p-3 bg-bg-light rounded-lg group border border-transparent hover:border-primary/30 transition-all">
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 bg-white rounded flex items-center justify-center text-primary border border-slate-200">
                                <span className="material-icons-round">{mimeIcon(f.mime_type)}</span>
                            </div>
                            <div>
                                <h4 className="text-sm font-bold">{f.filename}</h4>
                                <p className="text-[10px] text-slate-400 uppercase">
                                    {new Date(f.created_at).toLocaleDateString()} • {formatSize(f.size_bytes)}
                                </p>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => handleDelete(f.id)}
                            className="text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                        >
                            <span className="material-icons-round text-lg">delete_outline</span>
                        </button>
                    </div>
                ))}
            </div>

            {/* Upload zone */}
            <label className="border-2 border-dashed border-slate-200 rounded-xl p-8 flex flex-col items-center justify-center text-center group hover:border-primary transition-colors cursor-pointer bg-bg-light/50">
                <input type="file" onChange={handleUpload} className="hidden" accept=".pdf,.txt,.json,.csv,.zip,.pptx" />
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <span className="material-icons-round text-primary">
                        {uploading ? 'hourglass_top' : 'cloud_upload'}
                    </span>
                </div>
                <p className="font-bold text-sm">{uploading ? 'Uploading...' : 'Upload New Knowledge'}</p>
                <p className="text-xs text-slate-400 mt-1">PDF, TXT, PPTX, JSON, or CSV up to 50MB</p>
            </label>
        </div>
    )
}
