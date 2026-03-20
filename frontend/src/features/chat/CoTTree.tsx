import { useState } from 'react'
import type { CoTNode } from '@/types'
import './CoTTree.css'

interface CoTTreeProps {
    nodes: CoTNode[]
}

function CoTNodeItem({ node }: { node: CoTNode }) {
    const [expanded, setExpanded] = useState(true)

    const statusIndicator = {
        running: '🔄',
        completed: '✅',
        error: '❌',
    }[node.status]

    const duration =
        node.endTime != null
            ? `${((node.endTime - node.startTime) / 1000).toFixed(1)}s`
            : 'running...'

    return (
        <div className="cot-node">
            <button
                className="cot-node__header"
                onClick={() => setExpanded(!expanded)}
            >
                <span className="cot-node__toggle">{expanded ? '▾' : '▸'}</span>
                <span className="cot-node__status">{statusIndicator}</span>
                <span className="cot-node__name">{node.name}</span>
                <span className="cot-node__duration">{duration}</span>
            </button>

            {expanded && node.children.length > 0 && (
                <div className="cot-node__children">
                    {node.children.map((child) => (
                        <CoTNodeItem key={child.id} node={child} />
                    ))}
                </div>
            )}
        </div>
    )
}

export default function CoTTree({ nodes }: CoTTreeProps) {
    if (nodes.length === 0) return null

    return (
        <div className="cot-tree">
            <div className="cot-tree__header">
                <span className="cot-tree__label">Chain of Thought</span>
            </div>
            <div className="cot-tree__body">
                {nodes.map((node) => (
                    <CoTNodeItem key={node.id} node={node} />
                ))}
            </div>
        </div>
    )
}
