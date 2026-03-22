import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { createLogger } from '@/lib/logger'

const log = createLogger('ErrorBoundary')

interface Props {
    children: ReactNode
    fallback?: ReactNode
}

interface State {
    hasError: boolean
    error: Error | null
}

/**
 * 全局 React 错误边界。
 * 捕获子树中任何未处理的 render 阶段异常，显示降级 UI。
 */
export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props)
        this.state = { hasError: false, error: null }
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error }
    }

    componentDidCatch(error: Error, info: ErrorInfo): void {
        log.error('uncaught render error', { message: error.message, stack: info.componentStack })
    }

    private handleReload = (): void => {
        this.setState({ hasError: false, error: null })
        window.location.reload()
    }

    render(): ReactNode {
        if (!this.state.hasError) {
            return this.props.children
        }

        if (this.props.fallback) {
            return this.props.fallback
        }

        return (
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                gap: '1rem',
                padding: '2rem',
                fontFamily: 'system-ui, sans-serif',
                color: 'var(--text-primary, #111)',
                background: 'var(--surface-base, #fff)',
            }}>
                <div style={{
                    width: 56,
                    height: 56,
                    borderRadius: '50%',
                    background: 'var(--surface-raised, #f3f4f6)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 24,
                }}>
                    ⚠️
                </div>
                <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>
                    Something went wrong
                </h2>
                <p style={{
                    margin: 0,
                    fontSize: '0.875rem',
                    color: 'var(--text-muted, #6b7280)',
                    textAlign: 'center',
                    maxWidth: 400,
                }}>
                    {this.state.error?.message || 'An unexpected error occurred.'}
                </p>
                <button
                    onClick={this.handleReload}
                    style={{
                        marginTop: '0.5rem',
                        padding: '0.5rem 1.25rem',
                        borderRadius: '0.5rem',
                        border: '1px solid var(--border, #e5e7eb)',
                        background: 'var(--surface-raised, #f3f4f6)',
                        color: 'var(--text-primary, #111)',
                        cursor: 'pointer',
                        fontSize: '0.875rem',
                        fontWeight: 500,
                    }}
                >
                    Reload Page
                </button>
            </div>
        )
    }
}
