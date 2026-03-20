import { useRef, useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useDocuments, useDeleteDocument, useRetryParse, useInitiateUpload, useConfirmUpload } from '@/hooks/useDocuments'
import { useTranslation } from '@/i18n/useTranslation'
import api from '@/lib/api'
import './DocumentsPage.css'

export default function DocumentsPage() {
    const { id: workspaceId } = useParams<{ id: string }>()
    const { data: documents, isLoading } = useDocuments(workspaceId ?? '')
    const deleteDocument = useDeleteDocument()
    const retryParse = useRetryParse()
    const initiateUpload = useInitiateUpload()
    const confirmUpload = useConfirmUpload()
    const { t } = useTranslation()

    const fileInputRef = useRef<HTMLInputElement>(null)
    const [uploading, setUploading] = useState(false)
    const [dragOver, setDragOver] = useState(false)

    const statusBadgeClass: Record<string, string> = {
        completed: 'badge--success',
        parsing: 'badge--accent',
        pending: 'badge--warning',
        failed: 'badge--error',
        uploading: 'badge--warning',
    }

    const uploadFile = useCallback(async (file: File) => {
        if (!workspaceId) return
        setUploading(true)
        try {
            // Step 1: Get pre-signed upload URL
            const { document_id, upload_url } = await initiateUpload.mutateAsync({
                title: file.name.replace(/\.pdf$/i, ''),
                file_path: file.name,
                workspace_id: workspaceId,
            })

            // Step 2: Upload file to pre-signed URL
            await api.put(upload_url, file, {
                headers: { 'Content-Type': file.type },
            })

            // Step 3: Confirm upload to trigger parsing
            await confirmUpload.mutateAsync(document_id)
        } catch {
            // Error is visible via React Query error state
        } finally {
            setUploading(false)
        }
    }, [workspaceId, initiateUpload, confirmUpload])

    const handleFileSelect = useCallback((files: FileList | null) => {
        if (!files) return
        Array.from(files)
            .filter((f) => f.type === 'application/pdf')
            .forEach((f) => uploadFile(f))
    }, [uploadFile])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setDragOver(false)
        handleFileSelect(e.dataTransfer.files)
    }, [handleFileSelect])

    return (
        <div className="documents-page">
            <div className="documents-page__header">
                <div>
                    <h1>{t('documents.title')}</h1>
                    <p className="text-muted">{t('documents.subtitle')}</p>
                </div>
            </div>

            <div
                className={`file-dropzone ${dragOver ? 'file-dropzone--active' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    multiple
                    hidden
                    onChange={(e) => handleFileSelect(e.target.files)}
                />
                <div className="file-dropzone__content">
                    <div className="file-dropzone__icon">
                        {uploading ? '⏳' : '📎'}
                    </div>
                    <p>{uploading ? t('documents.uploading') : t('documents.dropzone')}</p>
                    <p className="text-muted">{t('documents.dropzoneHint')}</p>
                </div>
            </div>

            {isLoading && (
                <div className="documents-page__loading">{t('documents.loadingDocuments')}</div>
            )}

            <div className="documents-list">
                {documents?.map((doc) => (
                    <div key={doc.id} className="card document-item">
                        <div className="document-item__info">
                            <h3 className="document-item__title">{doc.title}</h3>
                            <div className="document-item__meta">
                                <span className={`badge ${statusBadgeClass[doc.parse_status] ?? 'badge--accent'}`}>
                                    {doc.parse_status}
                                </span>
                                {doc.year && <span className="text-muted">({doc.year})</span>}
                                {doc.doi && <span className="text-muted">{doc.doi}</span>}
                            </div>
                        </div>
                        <div className="document-item__actions">
                            {doc.parse_status === 'failed' && (
                                <button
                                    className="btn btn--ghost btn--sm"
                                    onClick={() => retryParse.mutate(doc.id)}
                                >
                                    {t('common.retry')}
                                </button>
                            )}
                            <button
                                className="btn btn--danger btn--sm"
                                onClick={() => deleteDocument.mutate(doc.id)}
                            >
                                {t('common.delete')}
                            </button>
                        </div>
                    </div>
                ))}

                {!isLoading && documents?.length === 0 && (
                    <div className="documents-page__empty">
                        <p>{t('documents.empty')}</p>
                    </div>
                )}
            </div>
        </div>
    )
}
