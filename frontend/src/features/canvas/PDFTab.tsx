import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileImage, Loader2 } from 'lucide-react'
import { useAgentStore } from '@/stores/useAgentStore'
import api from '@/lib/api'
import DocumentListPopover from './DocumentListPopover'

export default function PDFTab() {
    const activePdf = useAgentStore((s) => s.activePdf)
    const [pdfSrc, setPdfSrc] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const { id: workspaceId = '' } = useParams<{ id: string }>()

    useEffect(() => {
        if (!activePdf) return

        let isCancelled = false

        const fetchPdf = async () => {
            setLoading(true)
            try {
                const res = await api.get(`/documents/${activePdf.document_id}/download`, { responseType: 'blob' })
                if (isCancelled) return
                const url = URL.createObjectURL(res.data)
                setPdfSrc((prev) => {
                    if (prev) URL.revokeObjectURL(prev) // cleanup old
                    return url
                })
                setLoading(false)
            } catch {
                if (!isCancelled) setLoading(false)
            }
        }

        fetchPdf()

        return () => {
            isCancelled = true
        }
    }, [activePdf])

    // Cleanup object URL on unmount
    useEffect(() => {
        return () => {
            if (pdfSrc) URL.revokeObjectURL(pdfSrc)
        }
    }, [pdfSrc])

    if (!activePdf) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="flex items-center justify-center size-14 rounded-full bg-[var(--surface-raised)] mx-auto mb-3">
                        <FileImage className="size-6 text-[var(--text-muted)]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                        PDF Viewer
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] max-w-48 mx-auto">
                        An Agent workflow will display a PDF here when reading papers.
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-full bg-[var(--surface-raised)]">
            <div className="p-3 border-b border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text-secondary)] flex justify-between items-center">
                <div className="flex gap-2 items-center">
                    <DocumentListPopover workspaceId={workspaceId} />
                    <span className="w-px h-4 bg-[var(--border)]" />
                    <FileImage className="size-4 text-[var(--text-muted)]" />
                    <span className="font-mono">Doc: {activePdf.document_id.split('-')[0]}</span>
                    {activePdf.page > 0 && <span className="bg-[var(--accent-subtle)] text-[var(--accent)] px-2 py-0.5 rounded-full">Page {activePdf.page}</span>}
                </div>
                {activePdf.text_snippet && (
                    <div className="truncate max-w-[200px] italic text-[var(--text-muted)]" title={activePdf.text_snippet}>
                        "{activePdf.text_snippet}"
                    </div>
                )}
            </div>
            <div className="flex-1 relative bg-black/5 flex items-center justify-center border-t border-[var(--border)]">
                {loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-[var(--surface)]/50 backdrop-blur-sm z-10 transition-opacity">
                        <Loader2 className="size-6 text-[var(--accent)] animate-spin mb-2" />
                        <span className="text-xs text-[var(--text-muted)]">Loading PDF...</span>
                    </div>
                )}
                {pdfSrc ? (
                    <iframe
                        key={pdfSrc} // force re-render if memory URL changes
                        src={`${pdfSrc}#page=${activePdf.page || 1}&view=FitH`}
                        className="w-full h-full border-none"
                        title="PDF Viewer"
                    />
                ) : !loading && (
                    <div className="text-sm text-[var(--text-muted)]">Failed to load PDF</div>
                )}
            </div>
        </div>
    )
}
