import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import type { CoTNode } from '@/types'

interface CoTTreeProps {
    nodes: CoTNode[]
}

export default function CoTTree({ nodes }: CoTTreeProps) {
    if (nodes.length === 0) return null

    return (
        <div className="mx-6 my-3 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[var(--border)] bg-[var(--surface-raised)]">
                <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                    Chain of Thought
                </span>
            </div>
            <div className="p-2">
                {nodes.map((node) => (
                    <CoTNodeItem key={node.id} node={node} />
                ))}
            </div>
        </div>
    )
}

function CoTNodeItem({ node }: { node: CoTNode }) {
    const [expanded, setExpanded] = useState(node.status === 'running')
    const contentRef = useRef<HTMLDivElement>(null)

    // Auto-expand when running, auto-collapse when completed
    useEffect(() => {
        if (node.status === 'running') {
            setExpanded(true)
        }
    }, [node.status])

    const StatusIcon = {
        running: <Loader2 className="size-3.5 text-[var(--accent)] animate-spin" />,
        completed: <CheckCircle2 className="size-3.5 text-[var(--success)]" />,
        error: <XCircle className="size-3.5 text-[var(--error)]" />,
    }[node.status]

    const duration =
        node.endTime != null
            ? `${((node.endTime - node.startTime) / 1000).toFixed(1)}s`
            : 'running...'

    return (
        <div className="ml-1">
            <button
                className="flex items-center gap-1.5 w-full px-2 py-1 rounded-[var(--radius-sm)] text-left hover:bg-[var(--surface-raised)] transition-colors cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                {expanded
                    ? <ChevronDown className="size-3 text-[var(--text-muted)] shrink-0" />
                    : <ChevronRight className="size-3 text-[var(--text-muted)] shrink-0" />
                }
                {StatusIcon}
                <span className="text-xs font-mono text-[var(--text-secondary)] truncate">
                    {node.name}
                </span>
                <span className="text-[10px] text-[var(--text-muted)] ml-auto shrink-0">
                    {duration}
                </span>
            </button>

            <AnimatePresence>
                {expanded && node.children.length > 0 && (
                    <motion.div
                        ref={contentRef}
                        className="ml-4 border-l border-[var(--border)]"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.15, ease: 'easeOut' }}
                    >
                        {node.children.map((child) => (
                            <CoTNodeItem key={child.id} node={child} />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
