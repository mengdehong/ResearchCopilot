import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { DocumentMeta, DocumentStatus } from '@/types'

export function useDocuments(workspaceId: string, statusFilter?: string) {
    return useQuery<DocumentMeta[]>({
        queryKey: ['documents', workspaceId, statusFilter],
        queryFn: async () => {
            const params: Record<string, string> = { workspace_id: workspaceId }
            if (statusFilter) params.status_filter = statusFilter
            const { data } = await api.get('/documents', { params })
            return data
        },
        enabled: !!workspaceId,
    })
}

export function useDocumentStatus(documentId: string) {
    return useQuery<DocumentStatus>({
        queryKey: ['documents', documentId, 'status'],
        queryFn: async () => {
            const { data } = await api.get(`/documents/${documentId}/status`)
            return data
        },
        enabled: !!documentId,
        refetchInterval: 5000,
    })
}

export function useInitiateUpload() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (body: {
            title: string
            file_path: string
            workspace_id: string
        }) => {
            const { data } = await api.post('/documents/upload-url', body)
            return data as { document_id: string; upload_url: string; storage_key: string }
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ['documents', variables.workspace_id],
            })
        },
    })
}

export function useConfirmUpload() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (documentId: string) => {
            const { data } = await api.post('/documents/confirm', null, {
                params: { document_id: documentId },
            })
            return data as DocumentMeta
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['documents'] })
        },
    })
}

export function useRetryParse() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (documentId: string) => {
            const { data } = await api.post(`/documents/${documentId}/retry`)
            return data as DocumentMeta
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['documents'] })
        },
    })
}

export function useDeleteDocument() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (documentId: string) => {
            await api.delete(`/documents/${documentId}`)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['documents'] })
        },
    })
}
