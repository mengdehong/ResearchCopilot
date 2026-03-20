import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../useAuth'

export function GuestGuard() {
    const { isAuthenticated, isLoading } = useAuth()

    if (isLoading) {
        return (
            <div className="flex justify-center items-center h-screen w-full bg-slate-50 dark:bg-slate-900">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
        )
    }

    if (isAuthenticated) {
        return <Navigate to="/workspaces" replace />
    }

    return <Outlet />
}
