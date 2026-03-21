import { FileImage } from 'lucide-react'

export default function PDFTab() {
    return (
        <div className="flex items-center justify-center h-full">
            <div className="text-center">
                <div className="flex items-center justify-center size-14 rounded-full bg-[var(--surface-raised)] mx-auto mb-3">
                    <FileImage className="size-6 text-[var(--text-muted)]" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                    PDF Viewer
                </h3>
                <p className="text-xs text-[var(--text-muted)] max-w-48 mx-auto">
                    Select a document to view its PDF here.
                </p>
            </div>
        </div>
    )
}
