import { useLayoutStore } from '@/stores/useLayoutStore'
import { useAgentStore } from '@/stores/useAgentStore'
import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import EditorTab from './EditorTab'
import PDFTab from './PDFTab'
import SandboxTab from './SandboxTab'
import PaperSelectOverlay from './PaperSelectOverlay'
import type { CanvasTab, InterruptData } from '@/types'
import { FileText, FileImage, FlaskConical } from 'lucide-react'
import type { ReactNode } from 'react'

const TABS: { key: CanvasTab; label: string; icon: ReactNode }[] = [
    { key: 'editor', label: 'Editor', icon: <FileText className="size-3.5" /> },
    { key: 'pdf', label: 'PDF', icon: <FileImage className="size-3.5" /> },
    { key: 'sandbox', label: 'Sandbox', icon: <FlaskConical className="size-3.5" /> },
]

interface CanvasPanelProps {
    threadId: string
    interrupt: InterruptData | null
    onResumeInterrupt: (action: string, payload?: Record<string, unknown>) => void
}

export default function CanvasPanel({ threadId, interrupt, onResumeInterrupt }: CanvasPanelProps) {
    const activeTab = useLayoutStore((s) => s.activeCanvasTab)
    const setActiveTab = useLayoutStore((s) => s.setActiveCanvasTab)

    const activePdf = useAgentStore((s) => s.activePdf)
    const sandboxResult = useAgentStore((s) => s.sandboxResult)

    useEffect(() => {
        if (activePdf) setActiveTab('pdf')
    }, [activePdf, setActiveTab])

    useEffect(() => {
        if (sandboxResult) setActiveTab('sandbox')
    }, [sandboxResult, setActiveTab])

    const showPaperOverlay = interrupt?.action === 'select_papers'

    return (
        <div className="flex flex-col h-full bg-[var(--surface)]">
            {/* Tab Bar */}
            <div className="flex items-center gap-1 px-3 pt-2.5 border-b border-[var(--border)] bg-[var(--surface)] shrink-0">
                {TABS.map((tab) => (
                    <button
                        key={tab.key}
                        className={`
                            relative flex items-center gap-1.5 px-3 py-2 text-sm transition-colors cursor-pointer rounded-t-[var(--radius-sm)]
                            ${activeTab === tab.key
                                ? 'text-[var(--text-primary)] font-medium'
                                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                            }
                        `}
                        onClick={() => setActiveTab(tab.key)}
                    >
                        {tab.icon}
                        {tab.label}
                        {/* Active underline with layoutId animation */}
                        {activeTab === tab.key && (
                            <motion.div
                                className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent)]"
                                layoutId="canvas-tab-underline"
                                transition={{ type: 'spring', damping: 30, stiffness: 400 }}
                            />
                        )}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div className="relative flex-1 overflow-auto">
                {activeTab === 'editor' && <EditorTab threadId={threadId} />}
                {activeTab === 'pdf' && <PDFTab />}
                {activeTab === 'sandbox' && <SandboxTab />}

                {/* Paper Select Overlay */}
                <AnimatePresence>
                    {showPaperOverlay && interrupt && (
                        <PaperSelectOverlay
                            interrupt={interrupt}
                            onResume={onResumeInterrupt}
                            onClose={() => onResumeInterrupt('approve', { selected_ids: [] })}
                        />
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}
