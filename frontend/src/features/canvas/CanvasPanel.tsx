import { useLayoutStore } from '@/stores/useLayoutStore'
import { useAgentStore } from '@/stores/useAgentStore'
import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import EditorTab from './EditorTab'
import PDFTab from './PDFTab'
import SandboxTab from './SandboxTab'
import PaperSelectOverlay from './PaperSelectOverlay'
import type { CanvasTab, InterruptData } from '@/types'
import { FileText, FileImage, FlaskConical, Send, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n/useTranslation'
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
    const { t } = useTranslation()
    const activeTab = useLayoutStore((s) => s.activeCanvasTab)
    const setActiveTab = useLayoutStore((s) => s.setActiveCanvasTab)
    const pendingFinalizeReject = useLayoutStore((s) => s.pendingFinalizeReject)
    const setPendingFinalizeReject = useLayoutStore((s) => s.setPendingFinalizeReject)

    const activePdf = useAgentStore((s) => s.activePdf)
    const sandboxHistory = useAgentStore((s) => s.sandboxHistory)
    const editorHtml = useAgentStore((s) => s.editorHtml)

    useEffect(() => {
        if (activePdf) setActiveTab('pdf')
    }, [activePdf, setActiveTab])

    useEffect(() => {
        if (sandboxHistory.length > 0) setActiveTab('sandbox')
    }, [sandboxHistory, setActiveTab])

    const showPaperOverlay = interrupt?.action === 'select_papers'

    const handleSubmitEdits = () => {
        onResumeInterrupt('reject', { modified_markdown: editorHtml })
        setPendingFinalizeReject(false)
    }

    const handleCancelEdits = () => {
        setPendingFinalizeReject(false)
        onResumeInterrupt('approve')
    }

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
                <div className={`h-full ${activeTab === 'editor' ? 'block' : 'hidden'}`}>
                    <EditorTab threadId={threadId} />
                </div>
                <div className={`h-full ${activeTab === 'pdf' ? 'block' : 'hidden'}`}>
                    <PDFTab />
                </div>
                <div className={`h-full ${activeTab === 'sandbox' ? 'block' : 'hidden'}`}>
                    <SandboxTab />
                </div>

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

            {/* Finalize Submit Bar */}
            <AnimatePresence>
                {pendingFinalizeReject && activeTab === 'editor' && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="shrink-0 border-t border-[var(--accent)]/30 bg-[var(--accent-subtle)]/60 backdrop-blur-xl px-5 py-3 flex items-center gap-3"
                    >
                        <p className="flex-1 text-sm text-[var(--text-secondary)]">
                            {t('hitl.submitEditsHint')}
                        </p>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCancelEdits}
                            className="text-[var(--text-muted)]"
                        >
                            <X className="size-3.5 mr-1" />
                            {t('hitl.cancelEdits')}
                        </Button>
                        <Button size="sm" onClick={handleSubmitEdits}>
                            <Send className="size-3.5 mr-1" />
                            {t('hitl.submitEdits')}
                        </Button>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
