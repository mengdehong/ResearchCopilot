import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useDocuments, useDocumentStatus, useInitiateUpload, useConfirmUpload, useRetryParse, useDeleteDocument } from './useDocuments'

function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={ queryClient }> { children } </QueryClientProvider>
    }
}

describe('useDocuments', () => {
    it('fetches documents for a workspace', async () => {
        const { result } = renderHook(() => useDocuments('ws-1'), { wrapper: createWrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data).toHaveLength(1)
        expect(result.current.data![0].id).toBe('doc-1')
    })

    it('does not fetch when workspaceId is empty', () => {
        const { result } = renderHook(() => useDocuments(''), { wrapper: createWrapper() })
        expect(result.current.fetchStatus).toBe('idle')
    })
})

describe('useDocumentStatus', () => {
    it('fetches document status', async () => {
        const { result } = renderHook(() => useDocumentStatus('doc-1'), { wrapper: createWrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.parse_status).toBe('completed')
    })
})

describe('useInitiateUpload', () => {
    it('returns upload URL on success', async () => {
        const { result } = renderHook(() => useInitiateUpload(), { wrapper: createWrapper() })

        result.current.mutate({ title: 'Test', file_path: '/test.pdf', workspace_id: 'ws-1' })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.document_id).toBe('doc-new')
        expect(result.current.data!.upload_url).toContain('s3')
    })
})

describe('useConfirmUpload', () => {
    it('confirms upload and returns document', async () => {
        const { result } = renderHook(() => useConfirmUpload(), { wrapper: createWrapper() })

        result.current.mutate('doc-new')

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.parse_status).toBe('pending')
    })
})

describe('useRetryParse', () => {
    it('retries parse and returns document', async () => {
        const { result } = renderHook(() => useRetryParse(), { wrapper: createWrapper() })

        result.current.mutate('doc-1')

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})

describe('useDeleteDocument', () => {
    it('deletes document successfully', async () => {
        const { result } = renderHook(() => useDeleteDocument(), { wrapper: createWrapper() })

        result.current.mutate('doc-1')

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})
