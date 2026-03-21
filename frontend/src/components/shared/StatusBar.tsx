import { useAgentStore } from '@/stores/useAgentStore'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { useTranslation } from '@/i18n/useTranslation'
import { Loader2, Check } from 'lucide-react'

export default function StatusBar() {
    const currentNode = useAgentStore((s) => s.currentNode)
    const isStreaming = useAgentStore((s) => s.isStreaming)
    const saveStatus = useLayoutStore((s) => s.saveStatus)
    const { t } = useTranslation()

    return (
        <div className="flex items-center justify-between px-4 py-1.5 border-t border-[var(--border)] bg-[var(--surface)] text-xs select-none">
            <div className="flex items-center gap-2">
                {isStreaming ? (
                    <>
                        <span className="size-2 rounded-full bg-[var(--accent)] animate-[pulse-glow_2s_ease-in-out_infinite]" />
                        <span className="text-[var(--text-secondary)] font-mono truncate max-w-60">
                            {currentNode ?? t('status.processing')}
                        </span>
                    </>
                ) : (
                    <>
                        <span className="size-2 rounded-full bg-[var(--success)]" />
                        <span className="text-[var(--text-muted)]">{t('status.idle')}</span>
                    </>
                )}
            </div>

            <div className="flex items-center gap-1">
                {saveStatus === 'saving' && (
                    <span className="flex items-center gap-1 text-[var(--text-muted)]">
                        <Loader2 className="size-3 animate-spin" />
                        Saving...
                    </span>
                )}
                {saveStatus === 'saved' && (
                    <span className="flex items-center gap-1 text-[var(--success)]">
                        <Check className="size-3" />
                        Saved
                    </span>
                )}
            </div>

            <span className="text-[var(--text-muted)]">Research Copilot</span>
        </div>
    )
}
