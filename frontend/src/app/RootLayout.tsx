import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { LocaleProvider } from '@/i18n/context'
import { router } from './router'
import { AuthProvider } from '@/features/auth/AuthProvider'

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
        },
    },
})

export default function RootLayout() {
    return (
        <LocaleProvider>
            <AuthProvider>
                <QueryClientProvider client={queryClient}>
                    <RouterProvider router={router} />
                </QueryClientProvider>
            </AuthProvider>
        </LocaleProvider>
    )
}
