import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { ThreadInfo, RunRequest, RunResult, InterruptResponse, Message } from '@/types'

export function useThreads(workspaceId: string, limit?: number) {
    return useQuery<ThreadInfo[]>({
        queryKey: ['threads', workspaceId, limit ?? 'all'],
        queryFn: async () => {
            const params: Record<string, string | number> = { workspace_id: workspaceId }
            if (limit !== undefined) params.limit = limit
            const { data } = await api.get('/agent/threads', { params })
            return data
        },
        enabled: !!workspaceId,
    })
}

export function useMessages(threadId: string) {
    return useQuery<Message[]>({
        queryKey: ['messages', threadId],
        queryFn: async () => {
            const { data } = await api.get(`/agent/threads/${threadId}/messages`)
            return data
        },
        enabled: !!threadId,
        staleTime: 30_000,
    })
}

export function useCreateThread() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (params: { workspace_id: string; title?: string }) => {
            const { data } = await api.post('/agent/threads', null, {
                params: {
                    workspace_id: params.workspace_id,
                    title: params.title ?? 'New Thread',
                },
            })
            return data as ThreadInfo
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ['threads', variables.workspace_id],
            })
        },
    })
}

export function useCreateRun() {
    return useMutation({
        mutationFn: async (params: { threadId: string; body: RunRequest }) => {
            const { data } = await api.post(
                `/agent/threads/${params.threadId}/runs`,
                params.body,
            )
            return data as RunResult
        },
    })
}

export function useResumeRun() {
    return useMutation({
        mutationFn: async (params: {
            threadId: string
            runId: string
            body: InterruptResponse
        }) => {
            const { data } = await api.post(
                `/agent/threads/${params.threadId}/runs/${params.runId}/resume`,
                params.body,
            )
            return data as { run_id: string; status: string }
        },
    })
}

export function useCancelRun() {
    return useMutation({
        mutationFn: async (params: { threadId: string; runId: string }) => {
            await api.post(
                `/agent/threads/${params.threadId}/runs/${params.runId}/cancel`,
            )
        },
    })
}

export function useDeleteThread() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (params: { threadId: string; workspaceId: string }) => {
            await api.delete(`/agent/threads/${params.threadId}`)
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ['threads', variables.workspaceId],
            })
        },
    })
}
