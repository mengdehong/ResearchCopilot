import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/test-utils'
import { AuthGuard } from './AuthGuard'

function ProtectedContent() {
    return <div>Protected Page</div>
}

describe('AuthGuard', () => {
    it('renders child route when authenticated', () => {
        renderWithProviders(
            <Routes>
                <Route element={<AuthGuard />}>
                    <Route index element={<ProtectedContent />} />
                </Route>
            </Routes>,
            {
                authValue: {
                    user: { id: 'u-1', email: 'a@b.com', display_name: 'A' },
                    isAuthenticated: true,
                    isLoading: false,
                    login: () => { },
                    logout: async () => { },
                },
                routerProps: { initialEntries: ['/'] },
            },
        )
        expect(screen.getByText('Protected Page')).toBeInTheDocument()
    })

    it('redirects to /login when not authenticated', () => {
        renderWithProviders(
            <Routes>
                <Route element={<AuthGuard />}>
                    <Route index element={<ProtectedContent />} />
                </Route>
                <Route path="/login" element={<div>Login Page</div>} />
            </Routes>,
            {
                authValue: {
                    user: null,
                    isAuthenticated: false,
                    isLoading: false,
                    login: () => { },
                    logout: async () => { },
                },
                routerProps: { initialEntries: ['/'] },
            },
        )
        expect(screen.queryByText('Protected Page')).not.toBeInTheDocument()
        expect(screen.getByText('Login Page')).toBeInTheDocument()
    })

    it('shows spinner while loading', () => {
        renderWithProviders(
            <Routes>
                <Route element={<AuthGuard />}>
                    <Route index element={<ProtectedContent />} />
                </Route>
            </Routes>,
            {
                authValue: {
                    user: null,
                    isAuthenticated: false,
                    isLoading: true,
                    login: () => { },
                    logout: async () => { },
                },
                routerProps: { initialEntries: ['/'] },
            },
        )
        expect(screen.queryByText('Protected Page')).not.toBeInTheDocument()
        // Spinner has the animate-spin class
        const spinner = document.querySelector('.animate-spin')
        expect(spinner).toBeInTheDocument()
    })
})
