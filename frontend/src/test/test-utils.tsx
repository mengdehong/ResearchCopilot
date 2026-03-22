import React from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom'
import { AuthContext, type AuthContextType } from '@/features/auth/useAuth'

interface ExtendedRenderOptions extends Omit<RenderOptions, 'wrapper'> {
    authValue?: AuthContextType
    routerProps?: MemoryRouterProps
    queryClient?: QueryClient
}

const defaultAuth: AuthContextType = {
    user: { id: 'user-1', email: 'test@example.com', display_name: 'Test User' },
    isAuthenticated: true,
    isLoading: false,
    login: () => { },
    logout: async () => { },
}

function createTestQueryClient(): QueryClient {
    return new QueryClient({
        defaultOptions: {
            queries: { retry: false, gcTime: 0 },
            mutations: { retry: false },
        },
    })
}

/**
 * 便捷渲染函数，自动包裹 QueryClientProvider + MemoryRouter + AuthContext
 */
export function renderWithProviders(
    ui: React.ReactElement,
    {
        authValue = defaultAuth,
        routerProps = {},
        queryClient = createTestQueryClient(),
        ...renderOptions
    }: ExtendedRenderOptions = {},
) {
    function Wrapper({ children }: { children: React.ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                <AuthContext.Provider value={authValue}>
                    <MemoryRouter {...routerProps}>{children}</MemoryRouter>
                </AuthContext.Provider>
            </QueryClientProvider>
        )
    }

    return {
        ...render(ui, { wrapper: Wrapper, ...renderOptions }),
        queryClient,
    }
}

export { createTestQueryClient }
