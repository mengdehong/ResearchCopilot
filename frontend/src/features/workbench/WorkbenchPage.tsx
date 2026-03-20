import { useCallback, useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { useAgentStore } from '@/stores/useAgentStore'
import { useCreateThread, useCreateRun, useResumeRun } from '@/hooks/useThreads'
import { useSSE } from '@/hooks/useSSE'
import ChatPanel from '@/features/chat/ChatPanel'
import CanvasPanel from '@/features/canvas/CanvasPanel'
import StatusBar from '@/components/shared/StatusBar'
import './WorkbenchPage.css'

/**
 * Outer shell: uses key={workspaceId} to remount WorkbenchInner,
 * so useState naturally re-initializes without setState-in-effect.
 */
export default function WorkbenchPage() {
    const { id: workspaceId } = useParams<{ id: string }>()
    return <WorkbenchInner key={workspaceId} workspaceId={workspaceId ?? ''} />
}

function WorkbenchInner({ workspaceId }: { workspaceId: string }) {
    const splitRatio = useLayoutStore((s) => s.splitRatio)
    const addMessage = useAgentStore((s) => s.addMessage)
    const interrupt = useAgentStore((s) => s.interrupt)
    const clearInterrupt = useAgentStore((s) => s.clearInterrupt)
    const reset = useAgentStore((s) => s.reset)

    const [threadId, setThreadId] = useState('')
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

    // Reset agent store on mount (i.e. workspace change via key remount)
    useEffect(() => {
        reset()
    }, [reset])

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
        <div className="workbench-page">
            <div className="workbench-page__panels">
                <div
                    className="workbench-page__chat"
                    style={{ flexBasis: `${splitRatio * 100}%` }}
                >
                    <ChatPanel
                        threadId={threadId}
                        onSendMessage={handleSendMessage}
                        onResumeInterrupt={handleResumeInterrupt}
                    />
                </div>

                <div className="workbench-page__divider" />

                <div
                    className="workbench-page__canvas"
                    style={{ flexBasis: `${(1 - splitRatio) * 100}%` }}
                >
                    <CanvasPanel threadId={threadId} />
                </div>
            </div>

            <StatusBar />
        </div>
    )
}
