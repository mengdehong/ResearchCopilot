import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { DraftLoad } from '@/types'

export function useDraft(threadId: string) {
    return useQuery<DraftLoad>({
        queryKey: ['draft', threadId],
        queryFn: async () => {
            const { data } = await api.get(`/editor/draft/${threadId}`)
            return data
        },
        enabled: !!threadId,
        retry: false,
    })
}

export function useSaveDraft() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (params: { threadId: string; content: string }) => {
            const { data } = await api.put('/editor/draft', {
                content: params.content,
            }, {
                params: { thread_id: params.threadId },
            })
            return data as DraftLoad
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ['draft', variables.threadId],
            })
        },
    })
}
