import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { Workspace, WorkspaceCreate, WorkspaceSummary } from '@/types'

export function useWorkspaces() {
    return useQuery<Workspace[]>({
        queryKey: ['workspaces'],
        queryFn: async () => {
            const { data } = await api.get('/workspaces')
            return data
        },
    })
}

export function useWorkspace(id: string) {
    return useQuery<Workspace>({
        queryKey: ['workspaces', id],
        queryFn: async () => {
            const { data } = await api.get(`/workspaces/${id}`)
            return data
        },
        enabled: !!id,
    })
}

export function useWorkspaceSummary(id: string) {
    return useQuery<WorkspaceSummary>({
        queryKey: ['workspaces', id, 'summary'],
        queryFn: async () => {
            const { data } = await api.get(`/workspaces/${id}/summary`)
            return data
        },
        enabled: !!id,
    })
}

export function useCreateWorkspace() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (body: WorkspaceCreate) => {
            const { data } = await api.post('/workspaces', body)
            return data as Workspace
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['workspaces'] })
        },
    })
}

export function useDeleteWorkspace() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (id: string) => {
            await api.delete(`/workspaces/${id}`)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['workspaces'] })
        },
    })
}
