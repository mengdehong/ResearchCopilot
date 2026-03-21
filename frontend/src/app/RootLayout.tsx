import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { LocaleProvider } from '@/i18n/context'
import { router } from './router'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { useTheme } from '@/hooks/useTheme'
import { TooltipProvider } from '@/components/ui/tooltip'

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
    // Initialize theme (applies .dark class to <html> based on stored/system preference)
    useTheme()

    return (
        <LocaleProvider>
            <AuthProvider>
                <QueryClientProvider client={queryClient}>
                    <TooltipProvider>
                        <RouterProvider router={router} />
                    </TooltipProvider>
                </QueryClientProvider>
            </AuthProvider>
        </LocaleProvider>
    )
}
