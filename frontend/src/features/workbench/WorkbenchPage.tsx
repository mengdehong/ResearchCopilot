import { useCallback, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { useAgentStore } from '@/stores/useAgentStore'
import { useCreateThread, useCreateRun, useResumeRun } from '@/hooks/useThreads'
import { useSSE } from '@/hooks/useSSE'
import ChatPanel from '@/features/chat/ChatPanel'
import CanvasPanel from '@/features/canvas/CanvasPanel'

/**
 * Workbench page — no key-based remount; uses ref comparison
 * to reset agent store only when workspace actually changes.
 */
export default function WorkbenchPage() {
    const { id: workspaceId = '' } = useParams<{ id: string }>()
    const [searchParams] = useSearchParams()
    const threadParam = searchParams.get('thread') ?? ''
    const addMessage = useAgentStore((s) => s.addMessage)
    const interrupt = useAgentStore((s) => s.interrupt)
    const clearInterrupt = useAgentStore((s) => s.clearInterrupt)
    const reset = useAgentStore((s) => s.reset)

    const [threadId, setThreadId] = useState(threadParam)
    const [activeRunId, setActiveRunId] = useState('')

    const createThread = useCreateThread()
    const createRun = useCreateRun()
    const resumeRun = useResumeRun()

    // Wire SSE: connect when we have a threadId + activeRunId
    useSSE({
        threadId,
        runId: activeRunId,
        enabled: !!threadId && !!activeRunId,
    })

    // Reset agent store only when workspace changes (not on every mount)
    // Synchronous state initialization for render sync (React 18 compatible derived state pattern)
    const [prevWorkspace, setPrevWorkspace] = useState(workspaceId)
    if (workspaceId !== prevWorkspace) {
        setPrevWorkspace(workspaceId)
        setThreadId('')
        setActiveRunId('')
        reset()
    }

    // Sync threadId from URL query param when thread changes
    const [prevThreadParam, setPrevThreadParam] = useState(threadParam)
    if (threadParam && threadParam !== prevThreadParam) {
        setPrevThreadParam(threadParam)
        setThreadId(threadParam)
        setActiveRunId('')
        reset()
    }

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
                    setThreadId(currentThreadId)
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
        [addMessage, threadId, workspaceId, createThread, createRun],
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

    return (
        <div className="h-full w-full">
            <Group
                orientation="horizontal"
                className="h-full"
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
                    />
                </Panel>

                <Separator className="w-1 bg-[var(--border)] hover:bg-[var(--accent)]/40 active:bg-[var(--accent)]/60 transition-colors" />

                <Panel
                    defaultSize={60}
                    minSize={30}
                    className="h-full"
                >
                    <CanvasPanel threadId={threadId} />
                </Panel>
            </Group>
        </div>
    )
}
