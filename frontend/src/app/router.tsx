import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppLayout from './AppLayout'

/** Lazy-loaded page components */
import WorkspaceListPage from '@/features/workspace/WorkspaceListPage'
import WorkbenchPage from '@/features/workbench/WorkbenchPage'
import DocumentsPage from '@/features/documents/DocumentsPage'
import SettingsPage from '@/features/settings/SettingsPage'

export const router = createBrowserRouter([
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
])
