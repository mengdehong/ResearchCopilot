import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useWorkspaces, useWorkspace, useWorkspaceSummary, useCreateWorkspace, useDeleteWorkspace } from './useWorkspaces'

function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={ queryClient }> { children } </QueryClientProvider>
    }
}

describe('useWorkspaces', () => {
    it('fetches workspace list', async () => {
        const { result } = renderHook(() => useWorkspaces(), { wrapper: createWrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data).toHaveLength(1)
        expect(result.current.data![0].id).toBe('ws-1')
    })
})

describe('useWorkspace', () => {
    it('fetches single workspace by id', async () => {
        const { result } = renderHook(() => useWorkspace('ws-1'), { wrapper: createWrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.name).toBe('Workspace 1')
    })

    it('does not fetch when id is empty', () => {
        const { result } = renderHook(() => useWorkspace(''), { wrapper: createWrapper() })
        expect(result.current.fetchStatus).toBe('idle')
    })
})

describe('useWorkspaceSummary', () => {
    it('fetches workspace summary', async () => {
        const { result } = renderHook(() => useWorkspaceSummary('ws-1'), { wrapper: createWrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.document_count).toBe(3)
    })
})

describe('useCreateWorkspace', () => {
    it('creates workspace and returns it', async () => {
        const { result } = renderHook(() => useCreateWorkspace(), { wrapper: createWrapper() })

        result.current.mutate({ name: 'New WS', discipline: 'physics' })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.id).toBe('ws-new')
    })
})

describe('useDeleteWorkspace', () => {
    it('deletes workspace successfully', async () => {
        const { result } = renderHook(() => useDeleteWorkspace(), { wrapper: createWrapper() })

        result.current.mutate('ws-1')

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})
