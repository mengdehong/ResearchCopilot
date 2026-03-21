import { useAgentStore } from '@/stores/useAgentStore'
import { useTranslation } from '@/i18n/useTranslation'
import MessageList from './MessageList'
import InputArea from './InputArea'
import CoTTree from './CoTTree'
import HITLCard from './HITLCard'

interface ChatPanelProps {
    threadId: string
    onSendMessage: (message: string, files?: File[]) => void
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
        <div className="flex flex-col h-full">
            {/* Header with Agent Status */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border)] shrink-0">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                    {t('chat.title')}
                </h3>
                <AgentStatusIndicator isStreaming={isStreaming} />
            </div>

            {/* Message Area */}
            <div className="flex-1 overflow-auto">
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

            {/* Input */}
            <InputArea
                onSend={onSendMessage}
                disabled={isStreaming}
                threadId={threadId}
            />
        </div>
    )
}

/* ─── Agent Status ─── */
interface AgentStatusIndicatorProps {
    readonly isStreaming: boolean
}

function AgentStatusIndicator({ isStreaming }: AgentStatusIndicatorProps) {
    const { t } = useTranslation()

    if (!isStreaming) {
        return (
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                <span className="size-2 rounded-full bg-[var(--success)]" />
                {t('chat.idle')}
            </div>
        )
    }

    return (
        <div className="flex items-center gap-1.5 text-xs text-[var(--accent)]">
            <span className="size-2 rounded-full bg-[var(--accent)] animate-[pulse-glow_2s_ease-in-out_infinite]" />
            {t('chat.streaming')}
        </div>
    )
}
