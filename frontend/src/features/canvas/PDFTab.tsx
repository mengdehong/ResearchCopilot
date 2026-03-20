import './PDFTab.css'

export default function PDFTab() {
    return (
        <div className="pdf-tab">
            <div className="pdf-tab__empty">
                <div className="pdf-tab__icon">📄</div>
                <h3>PDF Viewer</h3>
                <p className="text-muted">
                    Select a document to view its PDF here.
                </p>
            </div>
        </div>
    )
}
