import { useState } from 'react'
import { useAgentStore } from '@/stores/useAgentStore'
import { Beaker, ChevronDown, ChevronRight } from 'lucide-react'
import type { ResearchBlock } from '@/types'
import { marked } from 'marked'

const WF_META: Record<string, { icon: string; label: string }> = {
    discovery: { icon: '📚', label: '文献发现' },
    extraction: { icon: '📝', label: '深度精读' },
    ideation: { icon: '💡', label: '研究构想' },
    execution: { icon: '⚙️', label: '代码执行' },
    critique: { icon: '🔍', label: '模拟审稿' },
    publish: { icon: '📄', label: '研究报告' },
}

function groupByWorkflow(blocks: ResearchBlock[]): Map<string, ResearchBlock[]> {
    const groups = new Map<string, ResearchBlock[]>()
    for (const block of blocks) {
        const key = block.workflow || 'unknown'
        const existing = groups.get(key) ?? []
        existing.push(block)
        groups.set(key, existing)
    }
    return groups
}

function WorkflowCard({ workflow, blocks }: { workflow: string; blocks: ResearchBlock[] }) {
    const [collapsed, setCollapsed] = useState(false)
    const meta = WF_META[workflow] ?? { icon: '📋', label: workflow }

    return (
        <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-sm">
            <button
                className="w-full flex items-center gap-2.5 px-4 py-3 text-left hover:bg-[var(--surface-raised)] transition-colors cursor-pointer"
                onClick={() => setCollapsed((prev) => !prev)}
            >
                <span className="text-base">{meta.icon}</span>
                <span className="text-sm font-semibold text-[var(--text-primary)] flex-1">
                    {meta.label}
                </span>
                <span className="text-[11px] text-[var(--text-muted)] tabular-nums">
                    {blocks.length}
                </span>
                {collapsed ? (
                    <ChevronRight className="size-4 text-[var(--text-muted)]" />
                ) : (
                    <ChevronDown className="size-4 text-[var(--text-muted)]" />
                )}
            </button>

            {!collapsed && (
                <div className="border-t border-[var(--border)] divide-y divide-[var(--border)]">
                    {blocks.map((block, idx) => {
                        const html = marked.parse(block.content)
                        return (
                            <div
                                key={`${workflow}-${idx}`}
                                className="px-4 py-3 text-sm text-[var(--text-secondary)] prose prose-sm max-w-none dark:prose-invert
                                    prose-headings:text-[var(--text-primary)] prose-headings:text-sm prose-headings:font-semibold
                                    prose-p:text-[var(--text-secondary)] prose-p:leading-relaxed
                                    prose-strong:text-[var(--text-primary)]
                                    prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1
                                    prose-li:text-[var(--text-secondary)]
                                    prose-code:text-[var(--accent)] prose-code:text-xs
                                    prose-pre:bg-[var(--surface-raised)] prose-pre:rounded-[var(--radius-sm)]"
                                dangerouslySetInnerHTML={{ __html: typeof html === 'string' ? html : '' }}
                            />
                        )
                    })}
                </div>
            )}
        </div>
    )
}

export default function ResearchTab() {
    const researchBlocks = useAgentStore((s) => s.researchBlocks)

    if (researchBlocks.length === 0) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="flex items-center justify-center size-14 rounded-full bg-[var(--surface-raised)] mx-auto mb-3">
                        <Beaker className="size-6 text-[var(--text-muted)]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                        Research
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] max-w-48 mx-auto">
                        各工作流的结构化产物将在这里展示。
                    </p>
                </div>
            </div>
        )
    }

    const grouped = groupByWorkflow(researchBlocks)
    const orderedKeys = ['discovery', 'extraction', 'ideation', 'execution', 'critique', 'publish']
    const sortedEntries = [...grouped.entries()].sort(([a], [b]) => {
        const ia = orderedKeys.indexOf(a)
        const ib = orderedKeys.indexOf(b)
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
    })

    return (
        <div className="flex flex-col h-full overflow-hidden bg-[var(--surface-raised)]">
            <div className="flex-1 p-5 overflow-auto space-y-3">
                {sortedEntries.map(([workflow, blocks]) => (
                    <WorkflowCard key={workflow} workflow={workflow} blocks={blocks} />
                ))}
            </div>
        </div>
    )
}
