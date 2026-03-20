import { useLayoutStore } from '@/stores/useLayoutStore'
import EditorTab from './EditorTab'
import PDFTab from './PDFTab'
import SandboxTab from './SandboxTab'
import type { CanvasTab } from '@/types'
import './CanvasPanel.css'

const TABS: { key: CanvasTab; label: string; icon: string }[] = [
    { key: 'editor', label: 'Editor', icon: '📝' },
    { key: 'pdf', label: 'PDF', icon: '📄' },
    { key: 'sandbox', label: 'Sandbox', icon: '🧪' },
]

interface CanvasPanelProps {
    threadId: string
}

export default function CanvasPanel({ threadId }: CanvasPanelProps) {
    const activeTab = useLayoutStore((s) => s.activeCanvasTab)
    const setActiveTab = useLayoutStore((s) => s.setActiveCanvasTab)

    return (
        <div className="canvas-panel">
            <div className="canvas-panel__tabs">
                {TABS.map((tab) => (
                    <button
                        key={tab.key}
                        className={`canvas-tab ${activeTab === tab.key ? 'canvas-tab--active' : ''}`}
                        onClick={() => setActiveTab(tab.key)}
                    >
                        <span className="canvas-tab__icon">{tab.icon}</span>
                        <span className="canvas-tab__label">{tab.label}</span>
                    </button>
                ))}
            </div>

            <div className="canvas-panel__content">
                {activeTab === 'editor' && <EditorTab threadId={threadId} />}
                {activeTab === 'pdf' && <PDFTab />}
                {activeTab === 'sandbox' && <SandboxTab />}
            </div>
        </div>
    )
}
