import { useCallback, useEffect, useState, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { MessageSquare, FileText } from 'lucide-react'
import { useAgentStore } from '@/stores/useAgentStore'
import { useCreateThread, useCreateRun, useResumeRun, useCancelRun, useMessages } from '@/hooks/useThreads'
import { useSSE } from '@/hooks/useSSE'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import ChatPanel from '@/features/chat/ChatPanel'
import CanvasPanel from '@/features/canvas/CanvasPanel'
import { useTranslation } from '@/i18n/useTranslation'

/**
 * Workbench page — threadId is always derived from URL `?thread=`.
 * Navigating away and back preserves thread since the URL is stable.
 */
export default function WorkbenchPage() {
    const { t } = useTranslation()
    const { id: workspaceId = '' } = useParams<{ id: string }>()
    const [searchParams, setSearchParams] = useSearchParams()

    // threadId is URL-driven: always read from ?thread=
    const threadId = searchParams.get('thread') ?? ''

    const addMessage = useAgentStore((s) => s.addMessage)
    const loadMessages = useAgentStore((s) => s.loadMessages)
    const interrupt = useAgentStore((s) => s.interrupt)
    const clearInterrupt = useAgentStore((s) => s.clearInterrupt)
    const reset = useAgentStore((s) => s.reset)
    const resetRunState = useAgentStore((s) => s.resetRunState)

    const [activeRunId, setActiveRunId] = useState('')

    const createThread = useCreateThread()
    const createRun = useCreateRun()
    const resumeRun = useResumeRun()
    const cancelRun = useCancelRun()
    const isMobile = useMediaQuery('(max-width: 768px)')
    const [mobileTab, setMobileTab] = useState<'chat' | 'canvas'>('chat')

    // Load chat history from backend when threadId changes
    const { data: historyMessages } = useMessages(threadId)
    const prevThreadRef = useRef(threadId)

    useEffect(() => {
        if (threadId !== prevThreadRef.current) {
            // Only reset when switching between existing threads, not on initial creation
            // (empty → newId means we just created a thread, run is already in progress)
            if (prevThreadRef.current !== '') {
                resetRunState()
                setActiveRunId('')
            }
            prevThreadRef.current = threadId
        }
    }, [threadId, resetRunState])

    useEffect(() => {
        if (historyMessages && historyMessages.length > 0) {
            // Only load history when store is empty (initial mount / return from navigation)
            // to avoid overwriting in-flight SSE messages during an active run
            const currentMessages = useAgentStore.getState().messages
            if (currentMessages.length === 0) {
                loadMessages(historyMessages)
            }
        }
    }, [historyMessages, loadMessages])

    // Reset everything when workspace changes
    const prevWorkspaceRef = useRef(workspaceId)
    useEffect(() => {
        if (workspaceId !== prevWorkspaceRef.current) {
            prevWorkspaceRef.current = workspaceId
            setActiveRunId('')
            reset()
        }
    }, [workspaceId, reset])

    // Wire SSE: connect when we have a threadId + activeRunId
    useSSE({
        threadId,
        runId: activeRunId,
        enabled: !!threadId && !!activeRunId,
    })

    const handleSendMessage = useCallback(
        async (message: string) => {
            addMessage({
                id: crypto.randomUUID(),
                role: 'user',
                content: message,
                timestamp: new Date().toISOString(),
            })

            let currentThreadId = threadId

            // Auto-create thread on first message
            if (!currentThreadId && workspaceId) {
                try {
                    const thread = await createThread.mutateAsync({
                        workspace_id: workspaceId,
                        title: message.slice(0, 50),
                    })
                    currentThreadId = thread.thread_id
                    setSearchParams({ thread: currentThreadId }, { replace: true })
                } catch {
                    addMessage({
                        id: crypto.randomUUID(),
                        role: 'system',
                        content: 'Failed to create thread. Please try again.',
                        timestamp: new Date().toISOString(),
                    })
                    return
                }
            }

            if (!currentThreadId) return

            try {
                const result = await createRun.mutateAsync({
                    threadId: currentThreadId,
                    body: { message },
                })
                setActiveRunId(result.run_id)
            } catch {
                addMessage({
                    id: crypto.randomUUID(),
                    role: 'system',
                    content: 'Failed to start agent run. Please try again.',
                    timestamp: new Date().toISOString(),
                })
            }
        },
        [addMessage, threadId, workspaceId, createThread, createRun, setSearchParams],
    )

    const handleResumeInterrupt = useCallback(
        async (action: string, payload?: Record<string, unknown>) => {
            if (!interrupt) return
            try {
                const result = await resumeRun.mutateAsync({
                    threadId: interrupt.thread_id,
                    runId: interrupt.run_id,
                    body: { action, payload },
                })
                clearInterrupt()
                setActiveRunId(result.run_id)
            } catch {
                // Keep interrupt visible so user can retry
            }
        },
        [interrupt, resumeRun, clearInterrupt],
    )

    const handleCancelRun = useCallback(async () => {
        if (!threadId || !activeRunId) return
        try {
            await cancelRun.mutateAsync({ threadId, runId: activeRunId })
        } finally {
            useAgentStore.setState({ isStreaming: false, currentNode: null })
            setActiveRunId('')
        }
    }, [threadId, activeRunId, cancelRun])

    if (isMobile) {
        return (
            <div className="h-full w-full flex flex-col">
                {/* Mobile Tab Bar */}
                <div className="flex items-center border-b border-[var(--border)] bg-[var(--surface)] shrink-0">
                    <button
                        className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-sm font-medium transition-colors cursor-pointer ${mobileTab === 'chat'
                            ? 'text-[var(--accent)] border-b-2 border-[var(--accent)]'
                            : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                            }`}
                        onClick={() => setMobileTab('chat')}
                    >
                        <MessageSquare className="size-4" />
                        {t('workbench.chat')}
                    </button>
                    <button
                        className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-sm font-medium transition-colors cursor-pointer ${mobileTab === 'canvas'
                            ? 'text-[var(--accent)] border-b-2 border-[var(--accent)]'
                            : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                            }`}
                        onClick={() => setMobileTab('canvas')}
                    >
                        <FileText className="size-4" />
                        {t('workbench.canvas')}
                    </button>
                </div>
                {/* Mobile Content */}
                <div className="flex-1 overflow-hidden">
                    {mobileTab === 'chat' ? (
                        <ChatPanel
                            threadId={threadId}
                            onSendMessage={handleSendMessage}
                            onResumeInterrupt={handleResumeInterrupt}
                            onCancelRun={handleCancelRun}
                        />
                    ) : (
                        <CanvasPanel
                            threadId={threadId}
                            interrupt={interrupt}
                            onResumeInterrupt={handleResumeInterrupt}
                        />
                    )}
                </div>
            </div>
        )
    }

    return (
        <div className="h-full w-full">
            <Group
                orientation="horizontal"
                className="h-full gap-0"
            >
                <Panel
                    defaultSize={40}
                    minSize={25}
                    className="h-full"
                >
                    <ChatPanel
                        threadId={threadId}
                        onSendMessage={handleSendMessage}
                        onResumeInterrupt={handleResumeInterrupt}
                        onCancelRun={handleCancelRun}
                    />
                </Panel>

                <Separator className="w-px bg-[var(--border)] hover:w-1 hover:bg-[var(--accent)]/40 active:bg-[var(--accent)]/60 transition-all duration-200" />

                <Panel
                    defaultSize={60}
                    minSize={30}
                    className="h-full"
                >
                    <CanvasPanel
                        threadId={threadId}
                        interrupt={interrupt}
                        onResumeInterrupt={handleResumeInterrupt}
                    />
                </Panel>
            </Group>
        </div>
    )
}
