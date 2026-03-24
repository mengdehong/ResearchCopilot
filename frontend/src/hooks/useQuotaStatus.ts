import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

interface WorkspaceQuota {
    readonly workspace_id: string
    readonly workspace_name: string
    readonly used_tokens: number
    readonly limit_tokens: number
}

interface QuotaStatus {
    readonly total_used: number
    readonly total_limit: number
    readonly remaining: number
    readonly usage_percent: number
    readonly workspaces: readonly WorkspaceQuota[]
}

export function useQuotaStatus() {
    return useQuery<QuotaStatus>({
        queryKey: ['quota', 'status'],
        queryFn: async () => {
            const { data } = await api.get('/quota/status')
            return data
        },
        staleTime: 60_000,
    })
}
