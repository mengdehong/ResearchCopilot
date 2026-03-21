import { useState } from 'react'
import { motion } from 'framer-motion'
import { FileText, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n/useTranslation'
import type { InterruptData } from '@/types'

interface Paper {
    id: string
    title: string
    abstract?: string
    relevance_comment?: string
    relevance_score?: number
    year?: number
}

interface PaperSelectOverlayProps {
    interrupt: InterruptData
    onResume: (action: string, payload?: Record<string, unknown>) => void
    onClose: () => void
}

export default function PaperSelectOverlay({
    interrupt,
    onResume,
    onClose,
}: PaperSelectOverlayProps) {
    const papers = (interrupt.payload.papers ?? interrupt.payload.candidates ?? []) as Paper[]
    const [selected, setSelected] = useState<Set<string>>(new Set())
    const { t } = useTranslation()

    const togglePaper = (id: string) => {
        setSelected((prev) => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }

    const toggleAll = () => {
        if (selected.size === papers.length) {
            setSelected(new Set())
        } else {
            setSelected(new Set(papers.map((p) => p.id)))
        }
    }

    const handleConfirm = () => {
        onResume('approve', { selected_ids: Array.from(selected) })
    }

    return (
        <motion.div
            className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[4px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
        >
            <motion.div
                className="glass-card flex flex-col w-[92%] max-h-[85%] rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)] overflow-hidden"
                initial={{ y: 24, opacity: 0, scale: 0.97 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                exit={{ y: 16, opacity: 0, scale: 0.97 }}
                transition={{ type: 'spring', damping: 28, stiffness: 350 }}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border)] bg-[var(--accent-subtle)]">
                    <div className="flex items-center gap-2">
                        <FileText className="size-4 text-[var(--accent)]" />
                        <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                            {t('hitl.selectPapers')}
                        </h4>
                        <span className="text-xs text-[var(--text-muted)] ml-1">
                            {papers.length} {t('hitl.papersFound', { count: String(papers.length) })}
                        </span>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 rounded-[var(--radius-sm)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)] transition-colors cursor-pointer"
                    >
                        <X className="size-4" />
                    </button>
                </div>

                {/* Select All Bar */}
                <div className="flex items-center gap-2 px-5 py-2 border-b border-[var(--border)] bg-[var(--surface)]">
                    <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={papers.length > 0 && selected.size === papers.length}
                            onChange={toggleAll}
                            className="accent-[var(--accent)]"
                        />
                        {t('hitl.selectAll')}
                    </label>
                    {selected.size > 0 && (
                        <span className="text-xs text-[var(--accent)] font-medium">
                            {t('hitl.selectedCount', { count: String(selected.size) })}
                        </span>
                    )}
                </div>

                {/* Paper List */}
                <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
                    {papers.map((p) => (
                        <label
                            key={p.id}
                            className={`
                                flex items-start gap-3 p-4 rounded-[var(--radius-md)] transition-all duration-200 cursor-pointer border active:scale-[0.99]
                                ${selected.has(p.id)
                                    ? 'bg-[var(--accent-subtle)] border-[var(--accent)]/40 shadow-sm'
                                    : 'bg-[var(--surface)] border-transparent hover:bg-[var(--surface-raised)] hover:border-[var(--border)] hover:shadow-sm'
                                }
                            `}
                        >
                            <input
                                type="checkbox"
                                checked={selected.has(p.id)}
                                onChange={() => togglePaper(p.id)}
                                className="mt-0.5 accent-[var(--accent)] shrink-0"
                            />
                            <div className="min-w-0 flex-1">
                                <div className="text-sm font-medium text-[var(--text-primary)] leading-snug">
                                    {p.title}
                                </div>
                                {p.relevance_comment && (
                                    <div className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed line-clamp-2">
                                        {p.relevance_comment}
                                    </div>
                                )}
                                <div className="flex items-center gap-2 mt-1.5">
                                    {p.year && (
                                        <span className="text-[10px] text-[var(--text-muted)] bg-[var(--surface-raised)] px-1.5 py-0.5 rounded-full">
                                            {p.year}
                                        </span>
                                    )}
                                    {p.relevance_score != null && (
                                        <span className="text-[10px] text-[var(--accent)] bg-[var(--accent-subtle)] px-1.5 py-0.5 rounded-full font-medium">
                                            {t('hitl.score')}: {p.relevance_score}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </label>
                    ))}
                    {papers.length === 0 && (
                        <p className="text-sm text-[var(--text-muted)] text-center py-8">
                            {t('hitl.noPapers')}
                        </p>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 px-5 py-3 border-t border-[var(--border)] bg-[var(--surface)]">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onClose}
                    >
                        {t('common.cancel')}
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleConfirm}
                        disabled={selected.size === 0}
                    >
                        {t('hitl.confirmSelection', { count: String(selected.size) })}
                    </Button>
                </div>
            </motion.div>
        </motion.div>
    )
}
