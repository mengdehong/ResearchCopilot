import './SandboxTab.css'

export default function SandboxTab() {
    return (
        <div className="sandbox-tab">
            <div className="sandbox-tab__empty">
                <div className="sandbox-tab__icon">🧪</div>
                <h3>Sandbox</h3>
                <p className="text-muted">
                    Code execution results will appear here.
                </p>
            </div>
        </div>
    )
}
