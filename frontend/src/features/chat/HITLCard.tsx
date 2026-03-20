import { useState } from 'react'
import type { InterruptData } from '@/types'
import { useTranslation } from '@/i18n/useTranslation'
import type { LocaleContextValue } from '@/i18n/LocaleContext'
import './HITLCard.css'

interface HITLCardProps {
    interrupt: InterruptData
    onResume: (action: string, payload?: Record<string, unknown>) => void
}

interface HITLInternalProps extends HITLCardProps {
    t: LocaleContextValue['t']
}

function SelectPapersCard({
    interrupt,
    onResume,
    t,
}: HITLInternalProps) {
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
        <div className="hitl-card">
            <div className="hitl-card__header">
                <span className="hitl-card__icon">📄</span>
                <h4>{t('hitl.selectPapers')}</h4>
            </div>
            <div className="hitl-card__body">
                {papers.map((p) => (
                    <label key={p.id} className="hitl-paper">
                        <input
                            type="checkbox"
                            checked={selected.has(p.id)}
                            onChange={() => togglePaper(p.id)}
                        />
                        <div className="hitl-paper__info">
                            <div className="hitl-paper__title">{p.title}</div>
                            {p.relevance_comment && (
                                <div className="hitl-paper__comment">{p.relevance_comment}</div>
                            )}
                        </div>
                    </label>
                ))}
                {papers.length === 0 && (
                    <p className="text-muted">{t('hitl.noPapers')}</p>
                )}
            </div>
            <div className="hitl-card__actions">
                <button
                    className="btn btn--primary"
                    onClick={() =>
                        onResume('approve', { selected_ids: Array.from(selected) })
                    }
                    disabled={selected.size === 0}
                >
                    {t('hitl.confirmSelection', { count: String(selected.size) })}
                </button>
            </div>
        </div>
    )
}

function ConfirmExecuteCard({
    interrupt,
    onResume,
    t,
}: HITLInternalProps) {
    const code = String(interrupt.payload.code ?? '')

    return (
        <div className="hitl-card">
            <div className="hitl-card__header">
                <span className="hitl-card__icon">⚡</span>
                <h4>{t('hitl.confirmExecute')}</h4>
            </div>
            <div className="hitl-card__body">
                <pre className="hitl-code">{code || t('hitl.noCode')}</pre>
            </div>
            <div className="hitl-card__actions">
                <button
                    className="btn btn--danger"
                    onClick={() => onResume('reject')}
                >
                    {t('common.reject')}
                </button>
                <button
                    className="btn btn--primary"
                    onClick={() => onResume('approve')}
                >
                    {t('hitl.approveExecute')}
                </button>
            </div>
        </div>
    )
}

function ConfirmFinalizeCard({
    interrupt,
    onResume,
    t,
}: HITLInternalProps) {
    const content = String(interrupt.payload.content ?? '')

    return (
        <div className="hitl-card">
            <div className="hitl-card__header">
                <span className="hitl-card__icon">📝</span>
                <h4>{t('hitl.confirmFinalize')}</h4>
            </div>
            <div className="hitl-card__body">
                <div className="hitl-preview">{content || t('hitl.noContent')}</div>
            </div>
            <div className="hitl-card__actions">
                <button
                    className="btn btn--ghost"
                    onClick={() => onResume('reject')}
                >
                    {t('hitl.editInCanvas')}
                </button>
                <button
                    className="btn btn--primary"
                    onClick={() => onResume('approve')}
                >
                    {t('common.approve')}
                </button>
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
                <div className="hitl-card">
                    <p>{t('hitl.unknownAction', { action: props.interrupt.action })}</p>
                </div>
            )
    }
}
