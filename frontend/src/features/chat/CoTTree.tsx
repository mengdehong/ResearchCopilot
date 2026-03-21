import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle, Brain } from 'lucide-react'
import type { CoTNode } from '@/types'

/** 内部节点名，不向用户展示 */
const INTERNAL_NODES = new Set([
    'RunnableSequence',
    'route_to_workflow',
    'route_after_eval',
    '__start__',
    '__end__',
])

/** 节点名中文映射 */
const NODE_LABELS: Record<string, string> = {
    supervisor: '决策分析',
    checkpoint_eval: '检查点评估',
    discovery: '论文检索',
    extraction: '深度精读',
    ideation: '实验设计',
    execution: '代码执行',
    critique: '模拟审稿',
    publish: '报告生成',
}

function getNodeLabel(name: string): string {
    return NODE_LABELS[name] ?? name
}

function filterInternalNodes(nodes: CoTNode[]): CoTNode[] {
    return nodes
        .filter((n) => !INTERNAL_NODES.has(n.name))
        .map((n) => ({
            ...n,
            children: filterInternalNodes(n.children),
        }))
}

interface CoTTreeProps {
    nodes: CoTNode[]
}

export default function CoTTree({ nodes }: CoTTreeProps) {
    const filtered = filterInternalNodes(nodes)
    if (filtered.length === 0) return null

    const isRunning = filtered.some(
        (n) => n.status === 'running' || n.children.some((c) => c.status === 'running'),
    )

    const [collapsed, setCollapsed] = useState(false)

    return (
        <div className="mx-6 my-3 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            {/* Clickable header — toggles entire CoT */}
            <button
                className="flex items-center gap-2 w-full px-3 py-2 border-b border-[var(--border)] bg-[var(--surface-raised)] hover:bg-[var(--surface-raised)]/80 transition-colors cursor-pointer"
                onClick={() => setCollapsed(!collapsed)}
            >
                {collapsed
                    ? <ChevronRight className="size-3 text-[var(--text-muted)]" />
                    : <ChevronDown className="size-3 text-[var(--text-muted)]" />
                }
                <Brain className="size-3.5 text-[var(--accent)]" />
                <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                    思考过程
                </span>
                {isRunning && (
                    <Loader2 className="size-3 text-[var(--accent)] animate-spin ml-auto" />
                )}
            </button>

            {/* Collapsible body */}
            <AnimatePresence>
                {!collapsed && (
                    <motion.div
                        className="p-2"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                    >
                        {filtered.map((node) => (
                            <CoTNodeItem key={node.id} node={node} />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

function CoTNodeItem({ node }: { node: CoTNode }) {
    const [expanded, setExpanded] = useState(node.status === 'running')
    const contentRef = useRef<HTMLDivElement>(null)

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
            : ''

    return (
        <div className="ml-1">
            <button
                className="flex items-center gap-1.5 w-full px-2 py-1 rounded-[var(--radius-sm)] text-left hover:bg-[var(--surface-raised)] transition-colors cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                {node.children.length > 0 && (
                    expanded
                        ? <ChevronDown className="size-3 text-[var(--text-muted)] shrink-0" />
                        : <ChevronRight className="size-3 text-[var(--text-muted)] shrink-0" />
                )}
                {StatusIcon}
                <span className="text-xs text-[var(--text-secondary)] truncate">
                    {getNodeLabel(node.name)}
                </span>
                {duration && (
                    <span className="text-[10px] text-[var(--text-muted)] ml-auto shrink-0">
                        {duration}
                    </span>
                )}
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
