import { FlaskConical, Terminal, Code2 } from 'lucide-react'
import { useAgentStore } from '@/stores/useAgentStore'

export default function SandboxTab() {
    const sandboxResult = useAgentStore((s) => s.sandboxResult)

    if (!sandboxResult) {
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

    return (
        <div className="flex flex-col h-full overflow-hidden bg-[var(--surface-raised)]">
            <div className="flex-1 p-5 overflow-auto space-y-6">

                {/* Code Block */}
                <div>
                    <div className="flex items-center gap-2 text-[var(--text-secondary)] font-medium mb-2.5 pb-2 border-b border-[var(--border)]">
                        <Code2 className="size-4" />
                        <span className="text-sm">Executed Code</span>
                    </div>
                    <pre className="text-xs font-mono bg-[var(--surface)] p-3.5 rounded-[var(--radius-md)] border border-[var(--border)] overflow-x-auto text-[var(--text-primary)] shadow-sm">
                        {sandboxResult.code || '// No code provided'}
                    </pre>
                </div>

                {/* Output Logs */}
                <div>
                    <div className="flex items-center justify-between mb-2.5 pb-2 border-b border-[var(--border)]">
                        <div className="flex items-center gap-2 text-[var(--text-secondary)] font-medium">
                            <Terminal className="size-4" />
                            <span className="text-sm">Execution Result</span>
                        </div>
                        <div className={`text-xs px-2.5 py-1 rounded-full font-medium ${sandboxResult.exit_code === 0 ? 'bg-[var(--success-subtle)] text-[var(--success)]' : 'bg-[var(--error-subtle)] text-[var(--error)]'}`}>
                            Exit Code: {sandboxResult.exit_code} <span className="opacity-70 font-normal">({sandboxResult.duration_ms}ms)</span>
                        </div>
                    </div>

                    {sandboxResult.stdout && (
                        <div className="mb-3">
                            <h4 className="text-[11px] font-semibold tracking-wider uppercase text-[var(--text-muted)] mb-1.5 pl-1">Standard Output</h4>
                            <pre className="text-xs font-mono text-[var(--text-primary)] bg-[var(--surface)] p-3.5 rounded-[var(--radius-md)] border border-[var(--border)] shadow-sm overflow-x-auto">
                                {sandboxResult.stdout}
                            </pre>
                        </div>
                    )}

                    {sandboxResult.stderr && (
                        <div className="mb-3">
                            <h4 className="text-[11px] font-semibold tracking-wider uppercase text-[var(--error)] mb-1.5 pl-1">Standard Error</h4>
                            <pre className="text-xs font-mono text-[var(--error)] bg-red-500/5 p-3.5 rounded-[var(--radius-md)] border border-red-500/20 shadow-sm overflow-x-auto">
                                {sandboxResult.stderr}
                            </pre>
                        </div>
                    )}

                    {(!sandboxResult.stdout && !sandboxResult.stderr) && (
                        <div className="text-[var(--text-muted)] italic text-sm p-4 text-center bg-[var(--surface)] rounded-[var(--radius-md)] border border-[var(--border)] border-dashed">
                            Code executed successfully with no output.
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
