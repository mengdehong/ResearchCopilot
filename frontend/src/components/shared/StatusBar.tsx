import { useAgentStore } from '@/stores/useAgentStore'
import { useTranslation } from '@/i18n/useTranslation'
import './StatusBar.css'

export default function StatusBar() {
    const currentNode = useAgentStore((s) => s.currentNode)
    const isStreaming = useAgentStore((s) => s.isStreaming)
    const { t } = useTranslation()

    return (
        <div className="status-bar">
            <div className="status-bar__left">
                {isStreaming ? (
                    <>
                        <span className="status-bar__dot status-bar__dot--active" />
                        <span className="status-bar__node">
                            {currentNode ?? t('status.processing')}
                        </span>
                    </>
                ) : (
                    <>
                        <span className="status-bar__dot status-bar__dot--idle" />
                        <span className="status-bar__text">{t('status.idle')}</span>
                    </>
                )}
            </div>
            <div className="status-bar__right">
                <span className="status-bar__text">Research Copilot</span>
            </div>
        </div>
    )
}
