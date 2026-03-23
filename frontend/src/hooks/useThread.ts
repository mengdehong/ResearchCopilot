import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type { ThreadDetail } from '@/types'

/**
 * Fetch a single thread's details, including `active_run_id` for SSE reconnection.
 */
export function useThread(threadId: string) {
    return useQuery<ThreadDetail>({
        queryKey: ['thread', threadId],
        queryFn: async () => {
            const { data } = await api.get(`/agent/threads/${threadId}`)
            return data as ThreadDetail
        },
        enabled: !!threadId,
        staleTime: 5_000,
    })
}
