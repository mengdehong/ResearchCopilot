import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useThreads, useCreateThread, useCreateRun, useResumeRun, useCancelRun, useDeleteThread } from './useThreads'

function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={ queryClient }> { children } </QueryClientProvider>
    }
}

describe('useThreads', () => {
    it('fetches threads for a workspace', async () => {
        const { result } = renderHook(() => useThreads('ws-1'), { wrapper: createWrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data).toHaveLength(1)
        expect(result.current.data![0].thread_id).toBe('th-1')
    })

    it('does not fetch when workspaceId is empty', () => {
        const { result } = renderHook(() => useThreads(''), { wrapper: createWrapper() })
        expect(result.current.fetchStatus).toBe('idle')
    })
})

describe('useCreateThread', () => {
    it('creates thread and returns ThreadInfo', async () => {
        const { result } = renderHook(() => useCreateThread(), { wrapper: createWrapper() })

        result.current.mutate({ workspace_id: 'ws-1', title: 'My Thread' })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.thread_id).toBe('th-new')
    })
})

describe('useCreateRun', () => {
    it('creates run and returns RunResult', async () => {
        const { result } = renderHook(() => useCreateRun(), { wrapper: createWrapper() })

        result.current.mutate({
            threadId: 'th-1',
            body: { message: 'Find papers on transformers' },
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data!.run_id).toBe('run-1')
        expect(result.current.data!.status).toBe('running')
    })
})

describe('useResumeRun', () => {
    it('resumes run successfully', async () => {
        const { result } = renderHook(() => useResumeRun(), { wrapper: createWrapper() })

        result.current.mutate({
            threadId: 'th-1',
            runId: 'run-1',
            body: { action: 'approve' },
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})

describe('useCancelRun', () => {
    it('cancels run successfully', async () => {
        const { result } = renderHook(() => useCancelRun(), { wrapper: createWrapper() })

        result.current.mutate({ threadId: 'th-1', runId: 'run-1' })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})

describe('useDeleteThread', () => {
    it('deletes thread successfully', async () => {
        const { result } = renderHook(() => useDeleteThread(), { wrapper: createWrapper() })

        result.current.mutate({ threadId: 'th-1', workspaceId: 'ws-1' })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})
