import { useState } from 'react'
import type { InterruptData } from '@/types'
import { useTranslation } from '@/i18n/useTranslation'
import type { LocaleContextValue } from '@/i18n/LocaleContext'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { FileText, Zap, FileEdit, AlertCircle } from 'lucide-react'

interface HITLCardProps {
    interrupt: InterruptData
    onResume: (action: string, payload?: Record<string, unknown>) => void
}

interface HITLInternalProps extends HITLCardProps {
    t: LocaleContextValue['t']
}

function SelectPapersCard({ interrupt, onResume, t }: HITLInternalProps) {
    const papers = (interrupt.payload.papers ?? []) as Array<{
        id: string
        title: string
        abstract?: string
        relevance_comment?: string
    }>
    const [selected, setSelected] = useState<Set<string>>(new Set())

    const togglePaper = (id: string) => {
        setSelected((prev) => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }

    return (
        <div className="mx-6 my-3 rounded-[var(--radius-md)] border-2 border-[var(--accent)] bg-[var(--surface)] overflow-hidden animate-[pulse-glow_2s_ease-in-out_2]">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)] bg-[var(--accent-subtle)]">
                <FileText className="size-4 text-[var(--accent)]" />
                <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                    {t('hitl.selectPapers')}
                </h4>
            </div>
            <div className="p-4 space-y-2 max-h-60 overflow-y-auto">
                {papers.map((p) => (
                    <label
                        key={p.id}
                        className="flex items-start gap-3 p-2 rounded-[var(--radius-sm)] hover:bg-[var(--surface-raised)] transition-colors cursor-pointer"
                    >
                        <input
                            type="checkbox"
                            checked={selected.has(p.id)}
                            onChange={() => togglePaper(p.id)}
                            className="mt-1 accent-[var(--accent)]"
                        />
                        <div className="min-w-0">
                            <div className="text-sm text-[var(--text-primary)] line-clamp-2">
                                {p.title}
                            </div>
                            {p.relevance_comment && (
                                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                                    {p.relevance_comment}
                                </div>
                            )}
                        </div>
                    </label>
                ))}
                {papers.length === 0 && (
                    <p className="text-sm text-[var(--text-muted)]">{t('hitl.noPapers')}</p>
                )}
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[var(--border)]">
                <Button
                    onClick={() =>
                        onResume('approve', { selected_ids: Array.from(selected) })
                    }
                    disabled={selected.size === 0}
                >
                    {t('hitl.confirmSelection', { count: String(selected.size) })}
                </Button>
            </div>
        </div>
    )
}

function ConfirmExecuteCard({ interrupt, onResume, t }: HITLInternalProps) {
    const code = String(interrupt.payload.code ?? '')

    return (
        <div className="mx-6 my-3 rounded-[var(--radius-md)] border-2 border-[var(--accent)] bg-[var(--surface)] overflow-hidden animate-[pulse-glow_2s_ease-in-out_2]">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)] bg-[var(--accent-subtle)]">
                <Zap className="size-4 text-[var(--accent)]" />
                <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                    {t('hitl.confirmExecute')}
                </h4>
            </div>
            <div className="p-4">
                <pre className="text-xs font-mono bg-[var(--surface-raised)] rounded-[var(--radius-sm)] p-3 overflow-x-auto text-[var(--text-secondary)]">
                    {code || t('hitl.noCode')}
                </pre>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[var(--border)]">
                <Popover>
                    <PopoverTrigger asChild>
                        <Button variant="ghost" className="text-[var(--error)]">
                            {t('common.reject')}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-56">
                        <div className="flex flex-col gap-2">
                            <p className="text-sm text-[var(--text-primary)]">
                                Are you sure you want to reject?
                            </p>
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => onResume('reject')}
                                className="w-full"
                            >
                                Confirm Reject
                            </Button>
                        </div>
                    </PopoverContent>
                </Popover>
                <Button onClick={() => onResume('approve')}>
                    {t('hitl.approveExecute')}
                </Button>
            </div>
        </div>
    )
}

function ConfirmFinalizeCard({ interrupt, onResume, t }: HITLInternalProps) {
    const content = String(interrupt.payload.content ?? '')

    return (
        <div className="mx-6 my-3 rounded-[var(--radius-md)] border-2 border-[var(--accent)] bg-[var(--surface)] overflow-hidden animate-[pulse-glow_2s_ease-in-out_2]">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)] bg-[var(--accent-subtle)]">
                <FileEdit className="size-4 text-[var(--accent)]" />
                <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                    {t('hitl.confirmFinalize')}
                </h4>
            </div>
            <div className="p-4">
                <div className="text-sm text-[var(--text-secondary)] bg-[var(--surface-raised)] rounded-[var(--radius-sm)] p-3 max-h-40 overflow-y-auto">
                    {content || t('hitl.noContent')}
                </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[var(--border)]">
                <Button variant="ghost" onClick={() => onResume('reject')}>
                    {t('hitl.editInCanvas')}
                </Button>
                <Button onClick={() => onResume('approve')}>
                    {t('common.approve')}
                </Button>
            </div>
        </div>
    )
}

export default function HITLCard(props: HITLCardProps) {
    const { t } = useTranslation()

    switch (props.interrupt.action) {
        case 'select_papers':
            return <SelectPapersCard {...props} t={t} />
        case 'confirm_execute':
            return <ConfirmExecuteCard {...props} t={t} />
        case 'confirm_finalize':
            return <ConfirmFinalizeCard {...props} t={t} />
        default:
            return (
                <div className="mx-6 my-3 p-4 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] flex items-center gap-2">
                    <AlertCircle className="size-4 text-[var(--warning)]" />
                    <p className="text-sm text-[var(--text-secondary)]">
                        {t('hitl.unknownAction', { action: props.interrupt.action })}
                    </p>
                </div>
            )
    }
}
