import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { Toaster, toast } from 'sonner'
import { LocaleProvider } from '@/i18n/context'
import { router } from './router'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { useTheme } from '@/hooks/useTheme'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ErrorBoundary } from '@/components/shared/ErrorBoundary'

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
        },
        mutations: {
            onError: (error: unknown) => {
                const message = error instanceof Error ? error.message : 'Operation failed'
                toast.error(message)
            },
        },
    },
})

export default function RootLayout() {
    // Initialize theme (applies .dark class to <html> based on stored/system preference)
    useTheme()

    return (
        <ErrorBoundary>
            <LocaleProvider>
                <AuthProvider>
                    <QueryClientProvider client={queryClient}>
                        <TooltipProvider>
                            <RouterProvider router={router} />
                        </TooltipProvider>
                        <Toaster
                            position="top-right"
                            richColors
                            closeButton
                            toastOptions={{
                                duration: 5000,
                                style: {
                                    fontFamily: 'var(--font-sans, system-ui, sans-serif)',
                                },
                            }}
                        />
                    </QueryClientProvider>
                </AuthProvider>
            </LocaleProvider>
        </ErrorBoundary>
    )
}
