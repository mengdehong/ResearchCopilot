import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppLayout from './AppLayout'
import { AuthGuard } from '@/features/auth/components/AuthGuard'
import { GuestGuard } from '@/features/auth/components/GuestGuard'
import { AuthLayout } from '@/features/auth/components/AuthLayout'

/** Lazy-loaded page components (Main App) */
import WorkspaceListPage from '@/features/workspace/WorkspaceListPage'
import WorkbenchPage from '@/features/workbench/WorkbenchPage'
import DocumentsPage from '@/features/documents/DocumentsPage'
import SettingsPage from '@/features/settings/SettingsPage'

/** Auth pages */
import LoginPage from '@/features/auth/pages/LoginPage'
import RegisterPage from '@/features/auth/pages/RegisterPage'
import VerifyEmailPage from '@/features/auth/pages/VerifyEmailPage'
import ForgotPasswordPage from '@/features/auth/pages/ForgotPasswordPage'
import ResetPasswordPage from '@/features/auth/pages/ResetPasswordPage'
import OAuthCallbackPage from '@/features/auth/pages/OAuthCallbackPage'

export const router = createBrowserRouter([
    // OAuth callback — public route, outside both guards
    {
        path: '/oauth/callback',
        element: <OAuthCallbackPage />,
    },
    {
        element: <GuestGuard />,
        children: [
            {
                element: <AuthLayout />,
                children: [
                    { path: '/login', element: <LoginPage /> },
                    { path: '/register', element: <RegisterPage /> },
                    { path: '/verify-email', element: <VerifyEmailPage /> },
                    { path: '/forgot-password', element: <ForgotPasswordPage /> },
                    { path: '/reset-password', element: <ResetPasswordPage /> },
                ],
            },
        ],
    },
    {
        element: <AuthGuard />,
        children: [
            {
                path: '/',
                element: <AppLayout />,
                children: [
                    { index: true, element: <Navigate to="/workspaces" replace /> },
                    { path: 'workspaces', element: <WorkspaceListPage /> },
                    { path: 'workspace/:id', element: <WorkbenchPage /> },
                    { path: 'workspace/:id/documents', element: <DocumentsPage /> },
                    { path: 'settings', element: <SettingsPage /> },
                ],
            },
        ],
    },
])
