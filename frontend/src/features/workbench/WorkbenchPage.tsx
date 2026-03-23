import { useCallback, useEffect, useState, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { MessageSquare, FileText } from 'lucide-react'
import { useAgentStore } from '@/stores/useAgentStore'
import type { InterruptData } from '@/types'
import { useCreateThread, useCreateRun, useResumeRun, useCancelRun, useMessages } from '@/hooks/useThreads'
import { useThread } from '@/hooks/useThread'
import { useSSE } from '@/hooks/useSSE'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import ChatPanel from '@/features/chat/ChatPanel'
import CanvasPanel from '@/features/canvas/CanvasPanel'
import { useTranslation } from '@/i18n/useTranslation'
import { createLogger } from '@/lib/logger'

const log = createLogger('Workbench')

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
    const { data: threadDetail } = useThread(threadId)

    const createThread = useCreateThread()
    const createRun = useCreateRun()
    const resumeRun = useResumeRun()
    const cancelRun = useCancelRun()
    const isMobile = useMediaQuery('(max-width: 768px)')
    const [mobileTab, setMobileTab] = useState<'chat' | 'canvas'>('chat')

    // Load chat history from backend when threadId changes
    const { data: messagesResponse } = useMessages(threadId)
    const prevThreadRef = useRef(threadId)
    // Track whether we just created this thread (skip reset in that case)
    const justCreatedRef = useRef(false)
    // Track which threadId we've already loaded history for — prevents re-runs on RQ refetch
    const historyLoadedForRef = useRef<string>('')

    useEffect(() => {
        if (threadId !== prevThreadRef.current) {
            if (justCreatedRef.current) {
                // We just created this thread ourselves — don't wipe the running state
                justCreatedRef.current = false
            } else {
                // Switching between threads: full reset so stale data is cleared out
                log.debug('thread switched', { from: prevThreadRef.current, to: threadId })
                reset()
                setActiveRunId('')
            }
            prevThreadRef.current = threadId
            // Allow history to load for the new thread
            historyLoadedForRef.current = ''
        }
    }, [threadId, reset])

    // SSE 重连：切回 thread 时，如果有 running run，自动恢复 SSE
    useEffect(() => {
        if (threadDetail?.active_run_id && !activeRunId) {
            log.info('restoring SSE for active run', { activeRunId: threadDetail.active_run_id })
            setActiveRunId(threadDetail.active_run_id)
        }
    }, [threadDetail, activeRunId])

    useEffect(() => {
        if (!messagesResponse) return
        const { messages: historyMsgs, pending_interrupt, cot_nodes, content_blocks } = messagesResponse
        if (historyLoadedForRef.current !== threadId) {
            historyLoadedForRef.current = threadId
            const currentMessages = useAgentStore.getState().messages
            if (currentMessages.length === 0) {
                loadMessages(historyMsgs)
            }
            // 恢复 Research Tab 的历史产物
            if (content_blocks && content_blocks.length > 0) {
                useAgentStore.getState().loadResearchBlocks(content_blocks)
            }
        }
        // 恢复 pending interrupt
        if (pending_interrupt && !useAgentStore.getState().interrupt) {
            useAgentStore.setState({ interrupt: pending_interrupt as InterruptData })
        }
        // 恢复 CoT 树（来自最后一个 RunSnapshot 的持久化数据）
        if (cot_nodes && cot_nodes.length > 0 && useAgentStore.getState().cotTree.length === 0) {
            const restoredTree = cot_nodes.map((n: { name: string }) => ({
                id: crypto.randomUUID(),
                name: n.name,
                startTime: 0,
                endTime: 0,
                children: [],
                status: 'completed' as const,
            }))
            useAgentStore.setState({ cotTree: restoredTree })
        }
    }, [messagesResponse, loadMessages, threadId])

    // Reset everything when workspace changes
    const prevWorkspaceRef = useRef(workspaceId)
    useEffect(() => {
        if (workspaceId !== prevWorkspaceRef.current) {
            log.debug('workspace switched', { from: prevWorkspaceRef.current, to: workspaceId })
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
            log.info('send message', { threadId, messageLength: message.length })
            // Clear previous run's CoT/streaming state — each turn has its own CoT
            resetRunState()
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
                    log.info('thread created', { threadId: currentThreadId })
                    justCreatedRef.current = true
                    setSearchParams({ thread: currentThreadId }, { replace: true })
                } catch {
                    log.error('thread creation failed', { workspaceId })
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
                log.info('run created', { threadId: currentThreadId, runId: result.run_id })
                setActiveRunId(result.run_id)
            } catch {
                log.error('run creation failed', { threadId: currentThreadId })
                addMessage({
                    id: crypto.randomUUID(),
                    role: 'system',
                    content: 'Failed to start agent run. Please try again.',
                    timestamp: new Date().toISOString(),
                })
            }
        },
        [addMessage, resetRunState, threadId, workspaceId, createThread, createRun, setSearchParams],
    )

    const handleResumeInterrupt = useCallback(
        async (action: string, payload?: Record<string, unknown>) => {
            if (!interrupt) return
            log.info('resume interrupt', { action, runId: interrupt.run_id })
            try {
                const result = await resumeRun.mutateAsync({
                    threadId: interrupt.thread_id,
                    runId: interrupt.run_id,
                    body: { action, payload },
                })
                clearInterrupt()
                setActiveRunId(result.run_id)
            } catch {
                log.error('resume interrupt failed', { runId: interrupt.run_id })
                // Keep interrupt visible so user can retry
            }
        },
        [interrupt, resumeRun, clearInterrupt],
    )

    const handleCancelRun = useCallback(async () => {
        if (!threadId || !activeRunId) return
        log.info('cancel run', { threadId, runId: activeRunId })
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
