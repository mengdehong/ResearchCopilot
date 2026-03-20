import { useAgentStore } from '@/stores/useAgentStore'
import { useTranslation } from '@/i18n/useTranslation'
import MessageList from './MessageList'
import InputArea from './InputArea'
import CoTTree from './CoTTree'
import HITLCard from './HITLCard'
import './ChatPanel.css'

interface ChatPanelProps {
    threadId: string
    onSendMessage: (message: string) => void
    onResumeInterrupt: (action: string, payload?: Record<string, unknown>) => void
}

export default function ChatPanel({
    threadId,
    onSendMessage,
    onResumeInterrupt,
}: ChatPanelProps) {
    const messages = useAgentStore((s) => s.messages)
    const cotTree = useAgentStore((s) => s.cotTree)
    const interrupt = useAgentStore((s) => s.interrupt)
    const isStreaming = useAgentStore((s) => s.isStreaming)
    const generatedContent = useAgentStore((s) => s.generatedContent)
    const { t } = useTranslation()

    return (
        <div className="chat-panel">
            <div className="chat-panel__header">
                <h3 className="chat-panel__title">{t('chat.title')}</h3>
                {isStreaming && <span className="badge badge--accent">{t('chat.streaming')}</span>}
            </div>

            <div className="chat-panel__body">
                <MessageList
                    messages={messages}
                    streamingContent={isStreaming ? generatedContent : undefined}
                />

                {cotTree.length > 0 && <CoTTree nodes={cotTree} />}

                {interrupt && (
                    <HITLCard
                        interrupt={interrupt}
                        onResume={onResumeInterrupt}
                    />
                )}
            </div>

            <InputArea
                onSend={onSendMessage}
                disabled={isStreaming}
                threadId={threadId}
            />
        </div>
    )
}
