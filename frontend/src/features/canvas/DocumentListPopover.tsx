import { useState, useRef } from 'react'
import { ChevronDown, FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import type { DocumentMeta } from '@/types'
import { useDocuments } from '@/hooks/useDocuments'
import { useAgentStore } from '@/stores/useAgentStore'

interface DocumentListPopoverProps {
    workspaceId: string
}

const statusIcon: Record<string, React.ReactNode> = {
    completed: <CheckCircle className="size-3 text-emerald-500" />,
    parsing: <Loader2 className="size-3 text-amber-400 animate-spin" />,
    pending: <Loader2 className="size-3 text-[var(--text-muted)] animate-spin" />,
    failed: <AlertCircle className="size-3 text-red-400" />,
}

export default function DocumentListPopover({ workspaceId }: DocumentListPopoverProps) {
    const [open, setOpen] = useState(false)
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const { data: documents } = useDocuments(workspaceId, 'completed')
    const activePdf = useAgentStore((s) => s.activePdf)
    const setActivePdf = useAgentStore((s) => s.setActivePdf)

    const handleMouseEnter = () => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        setOpen(true)
    }

    const handleMouseLeave = () => {
        timeoutRef.current = setTimeout(() => setOpen(false), 200)
    }

    const handleSelect = (doc: DocumentMeta) => {
        setActivePdf({ document_id: doc.id, page: 1, bbox: [], text_snippet: '' })
        setOpen(false)
    }

    if (!documents || documents.length === 0) return null

    return (
        <div
            className="relative"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <button
                id="document-list-toggle"
                className="flex items-center gap-1 px-2 py-1 rounded-md text-xs
                    text-[var(--text-secondary)] hover:bg-[var(--surface-raised)]
                    hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                onClick={() => setOpen((v) => !v)}
            >
                <FileText className="size-3.5" />
                <span>{documents.length}</span>
                <ChevronDown className={`size-3 transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>

            {open && (
                <div
                    className="absolute left-0 top-full mt-1 z-50 min-w-[240px] max-h-[320px]
                        overflow-y-auto rounded-lg border border-[var(--border)]
                        bg-[var(--surface)] shadow-xl backdrop-blur-md"
                >
                    <div className="px-3 py-2 border-b border-[var(--border)]">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                            Imported Documents
                        </span>
                    </div>
                    {documents.map((doc) => {
                        const isActive = activePdf?.document_id === doc.id
                        return (
                            <button
                                key={doc.id}
                                id={`doc-item-${doc.id}`}
                                onClick={() => handleSelect(doc)}
                                className={`w-full flex items-center gap-2 px-3 py-2 text-left text-xs
                                    transition-colors hover:bg-[var(--surface-raised)] cursor-pointer
                                    ${isActive ? 'bg-[var(--accent-subtle)] text-[var(--accent)]' : 'text-[var(--text-secondary)]'}`}
                            >
                                {statusIcon[doc.parse_status] ?? <FileText className="size-3 text-[var(--text-muted)]" />}
                                <span className="truncate flex-1" title={doc.title}>
                                    {doc.title}
                                </span>
                                {doc.source === 'arxiv' && (
                                    <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400">
                                        arXiv
                                    </span>
                                )}
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
