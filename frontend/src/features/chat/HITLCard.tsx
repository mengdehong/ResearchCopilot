import type { InterruptData } from '@/types'
import { useTranslation } from '@/i18n/useTranslation'
import type { LocaleContextValue } from '@/i18n/LocaleContext'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { FileText, Zap, FileEdit, AlertCircle, Loader2 } from 'lucide-react'

interface HITLCardProps {
    interrupt: InterruptData
    onResume: (action: string, payload?: Record<string, unknown>) => void
}

interface HITLInternalProps extends HITLCardProps {
    t: LocaleContextValue['t']
}

function SelectPapersCard({ t }: HITLInternalProps) {
    return (
        <div className="mx-6 my-4 rounded-2xl border border-[var(--accent)]/30 bg-[var(--accent-subtle)]/50 backdrop-blur-xl px-5 py-4 flex items-center gap-3 animate-[pulse-glow_2s_ease-in-out_2] shadow-[var(--shadow-sm)]">
            <FileText className="size-5 text-[var(--accent)] shrink-0" />
            <p className="text-sm text-[var(--text-secondary)]">
                {t('hitl.paperListOnRight')}
            </p>
        </div>
    )
}

function ConfirmExecuteCard({ interrupt, onResume, t }: HITLInternalProps) {
    const code = String(interrupt.payload.code ?? '')

    return (
        <div className="mx-6 my-4 rounded-2xl border border-[var(--accent)]/40 bg-[var(--surface)]/80 backdrop-blur-xl overflow-hidden shadow-[var(--shadow-md)] animate-[pulse-glow_2s_ease-in-out_2]">
            <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-[var(--border)] bg-[var(--accent-subtle)]/50">
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
                                {t('hitl.rejectConfirm')}
                            </p>
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => onResume('reject')}
                                className="w-full"
                            >
                                {t('hitl.confirmReject')}
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
    const setActiveCanvasTab = useLayoutStore((s) => s.setActiveCanvasTab)
    const setPendingFinalizeReject = useLayoutStore((s) => s.setPendingFinalizeReject)

    const handleEditInCanvas = () => {
        setPendingFinalizeReject(true)
        setActiveCanvasTab('editor')
    }

    return (
        <div className="mx-6 my-4 rounded-2xl border border-[var(--accent)]/40 bg-[var(--surface)]/80 backdrop-blur-xl overflow-hidden shadow-[var(--shadow-md)] animate-[pulse-glow_2s_ease-in-out_2]">
            <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-[var(--border)] bg-[var(--accent-subtle)]/50">
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
                <Button variant="ghost" onClick={handleEditInCanvas}>
                    {t('hitl.editInCanvas')}
                </Button>
                <Button onClick={() => onResume('approve')}>
                    {t('common.approve')}
                </Button>
            </div>
        </div>
    )
}

function WaitForIngestionCard({ t }: HITLInternalProps) {
    return (
        <div className="mx-6 my-4 rounded-2xl border border-[var(--accent)]/30 bg-[var(--accent-subtle)]/50 backdrop-blur-xl px-5 py-4 flex items-center gap-3 shadow-[var(--shadow-sm)]">
            <Loader2 className="size-5 text-[var(--accent)] shrink-0 animate-spin" />
            <p className="text-sm text-[var(--text-secondary)]">
                {t('hitl.waitForIngestion')}
            </p>
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
        case 'wait_for_ingestion':
            return <WaitForIngestionCard {...props} t={t} />
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
