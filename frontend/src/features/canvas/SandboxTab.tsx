import { useEffect, useState } from 'react'
import { FlaskConical, Terminal, Code2, ImageIcon, ChevronLeft, ChevronRight } from 'lucide-react'
import { useAgentStore } from '@/stores/useAgentStore'
import type { SandboxResult } from '@/types'

function imageDataUri(name: string, data: string): string {
    const ext = name.split('.').pop()?.toLowerCase() ?? 'png'
    const mime = ext === 'svg' ? 'image/svg+xml' : `image/${ext}`
    return `data:${mime};base64,${data}`
}

function ResultView({ result }: { result: SandboxResult }) {
    return (
        <div className="space-y-6">
            {/* Code Block */}
            <div>
                <div className="flex items-center gap-2 text-[var(--text-secondary)] font-medium mb-2.5 pb-2 border-b border-[var(--border)]">
                    <Code2 className="size-4" />
                    <span className="text-sm">Executed Code</span>
                </div>
                <pre className="text-xs font-mono bg-[var(--surface)] p-3.5 rounded-[var(--radius-md)] border border-[var(--border)] overflow-x-auto text-[var(--text-primary)] shadow-sm">
                    {result.code || '// No code provided'}
                </pre>
            </div>

            {/* Execution Result */}
            <div>
                <div className="flex items-center justify-between mb-2.5 pb-2 border-b border-[var(--border)]">
                    <div className="flex items-center gap-2 text-[var(--text-secondary)] font-medium">
                        <Terminal className="size-4" />
                        <span className="text-sm">Execution Result</span>
                    </div>
                    <div className={`text-xs px-2.5 py-1 rounded-full font-medium ${result.exit_code === 0 ? 'bg-[var(--success-subtle)] text-[var(--success)]' : 'bg-[var(--error-subtle)] text-[var(--error)]'}`}>
                        Exit Code: {result.exit_code} <span className="opacity-70 font-normal">({result.duration_ms}ms)</span>
                    </div>
                </div>

                {result.stdout && (
                    <div className="mb-3">
                        <h4 className="text-[11px] font-semibold tracking-wider uppercase text-[var(--text-muted)] mb-1.5 pl-1">Standard Output</h4>
                        <pre className="text-xs font-mono text-[var(--text-primary)] bg-[var(--surface)] p-3.5 rounded-[var(--radius-md)] border border-[var(--border)] shadow-sm overflow-x-auto">
                            {result.stdout}
                        </pre>
                    </div>
                )}

                {result.stderr && (
                    <div className="mb-3">
                        <h4 className="text-[11px] font-semibold tracking-wider uppercase text-[var(--error)] mb-1.5 pl-1">Standard Error</h4>
                        <pre className="text-xs font-mono text-[var(--error)] bg-red-500/5 p-3.5 rounded-[var(--radius-md)] border border-red-500/20 shadow-sm overflow-x-auto">
                            {result.stderr}
                        </pre>
                    </div>
                )}

                {(!result.stdout && !result.stderr) && (
                    <div className="text-[var(--text-muted)] italic text-sm p-4 text-center bg-[var(--surface)] rounded-[var(--radius-md)] border border-[var(--border)] border-dashed">
                        Code executed successfully with no output.
                    </div>
                )}
            </div>

            {/* Output Images */}
            {result.images.length > 0 && (
                <div>
                    <div className="flex items-center gap-2 text-[var(--text-secondary)] font-medium mb-2.5 pb-2 border-b border-[var(--border)]">
                        <ImageIcon className="size-4" />
                        <span className="text-sm">Output Files</span>
                        <span className="text-xs text-[var(--text-muted)] font-normal">({result.images.length})</span>
                    </div>
                    <div className="flex flex-col gap-3">
                        {result.images.map((img, idx) => (
                            <div key={`${img.name}-${idx}`} className="rounded-[var(--radius-md)] border border-[var(--border)] overflow-hidden shadow-sm">
                                <p className="text-[11px] text-[var(--text-muted)] px-3 py-1.5 bg-[var(--surface)] border-b border-[var(--border)] font-mono">
                                    {img.name}
                                </p>
                                <img
                                    src={imageDataUri(img.name, img.data)}
                                    alt={img.name}
                                    className="max-w-full h-auto block bg-white"
                                />
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default function SandboxTab() {
    const sandboxHistory = useAgentStore((s) => s.sandboxHistory)
    const [index, setIndex] = useState<number | null>(null)

    // Auto-jump to latest result when new executions arrive
    useEffect(() => {
        setIndex(null)
    }, [sandboxHistory.length])

    if (sandboxHistory.length === 0) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="flex items-center justify-center size-14 rounded-full bg-[var(--surface-raised)] mx-auto mb-3">
                        <FlaskConical className="size-6 text-[var(--text-muted)]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                        Sandbox
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] max-w-48 mx-auto">
                        Agent code execution results will appear here.
                    </p>
                </div>
            </div>
        )
    }

    // null = latest run
    const currentIndex = index ?? sandboxHistory.length - 1
    const result = sandboxHistory[currentIndex]
    const total = sandboxHistory.length

    return (
        <div className="flex flex-col h-full overflow-hidden bg-[var(--surface-raised)]">
            {/* History navigation — only shown when more than one run */}
            {total > 1 && (
                <div className="flex items-center justify-center gap-3 px-4 py-2 border-b border-[var(--border)] bg-[var(--surface)] shrink-0">
                    <button
                        className="p-1 rounded hover:bg-[var(--surface-raised)] disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed transition-colors"
                        disabled={currentIndex === 0}
                        onClick={() => setIndex(currentIndex - 1)}
                        aria-label="Previous execution"
                    >
                        <ChevronLeft className="size-4 text-[var(--text-secondary)]" />
                    </button>
                    <span className="text-xs text-[var(--text-muted)] tabular-nums">
                        Run {currentIndex + 1} / {total}
                    </span>
                    <button
                        className="p-1 rounded hover:bg-[var(--surface-raised)] disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed transition-colors"
                        disabled={currentIndex === total - 1}
                        onClick={() => setIndex(currentIndex + 1)}
                        aria-label="Next execution"
                    >
                        <ChevronRight className="size-4 text-[var(--text-secondary)]" />
                    </button>
                </div>
            )}

            <div className="flex-1 p-5 overflow-auto">
                <ResultView result={result} />
            </div>
        </div>
    )
}
