import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { Workspace, WorkspaceCreate, WorkspaceSummary } from '@/types'
import { createLogger } from '@/lib/logger'

const log = createLogger('Workspace')

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
        onSuccess: (data) => {
            log.info('workspace created', { id: data.id, name: data.name })
            queryClient.invalidateQueries({ queryKey: ['workspaces'] })
        },
        onError: (error: Error) => {
            log.error('workspace creation failed', { error: error.message })
        },
    })
}

export function useDeleteWorkspace() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (id: string) => {
            await api.delete(`/workspaces/${id}`)
        },
        onSuccess: (_data, id) => {
            log.info('workspace deleted', { id })
            queryClient.invalidateQueries({ queryKey: ['workspaces'] })
        },
        onError: (error: Error) => {
            log.error('workspace deletion failed', { error: error.message })
        },
    })
}
