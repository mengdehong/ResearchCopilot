import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/test-utils'
import { GuestGuard } from './GuestGuard'

function LoginContent() {
    return <div>Login Form</div>
}

describe('GuestGuard', () => {
    it('renders child route when not authenticated', () => {
        renderWithProviders(
            <Routes>
                <Route element={<GuestGuard />}>
                    <Route index element={<LoginContent />} />
                </Route>
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
        expect(screen.getByText('Login Form')).toBeInTheDocument()
    })

    it('redirects to /workspaces when authenticated', () => {
        renderWithProviders(
            <Routes>
                <Route element={<GuestGuard />}>
                    <Route index element={<LoginContent />} />
                </Route>
                <Route path="/workspaces" element={<div>Workspaces Page</div>} />
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
        expect(screen.queryByText('Login Form')).not.toBeInTheDocument()
        expect(screen.getByText('Workspaces Page')).toBeInTheDocument()
    })

    it('shows spinner while loading', () => {
        renderWithProviders(
            <Routes>
                <Route element={<GuestGuard />}>
                    <Route index element={<LoginContent />} />
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
        expect(screen.queryByText('Login Form')).not.toBeInTheDocument()
        const spinner = document.querySelector('.animate-spin')
        expect(spinner).toBeInTheDocument()
    })
})
