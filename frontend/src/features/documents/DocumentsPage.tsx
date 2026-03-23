import { useRef, useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import { useDocuments, useDeleteDocument, useRetryParse, useInitiateUpload, useConfirmUpload } from '@/hooks/useDocuments'
import { useTranslation } from '@/i18n/useTranslation'
import api from '@/lib/api'
import { Upload, FileText, Trash2, RotateCcw, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { FadeIn, StaggerContainer, StaggerItem } from '@/components/shared/MotionWrappers'

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
    completed: 'success',
    parsing: 'default',
    pending: 'warning',
    failed: 'destructive',
    uploading: 'warning',
}

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
    const [uploadError, setUploadError] = useState<string | null>(null)

    const uploadFile = useCallback(async (file: File) => {
        if (!workspaceId) return
        setUploading(true)
        setUploadError(null)
        try {
            const { document_id, upload_url } = await initiateUpload.mutateAsync({
                title: file.name.replace(/\.pdf$/i, ''),
                file_path: file.name,
                workspace_id: workspaceId,
            })

            await api.put(upload_url, file, {
                headers: { 'Content-Type': file.type },
            })

            await confirmUpload.mutateAsync(document_id)
        } catch (err) {
            let message = t('documents.uploadError')
            if (axios.isAxiosError(err)) {
                const detail = err.response?.data?.detail
                message = typeof detail === 'string' ? detail : err.message
            } else if (err instanceof Error) {
                message = err.message
            }
            setUploadError(`${file.name}: ${message}`)
        } finally {
            setUploading(false)
        }
    }, [workspaceId, initiateUpload, confirmUpload, t])

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
        <div className="h-full overflow-auto p-6 md:p-10">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                    {t('documents.title')}
                </h1>
                <p className="text-sm text-[var(--text-secondary)] mt-1">
                    {t('documents.subtitle')}
                </p>
            </div>

            {/* Dropzone */}
            <div
                className={`
                    relative flex flex-col items-center justify-center p-8 mb-6 rounded-[var(--radius-lg)]
                    border-2 border-dashed transition-all cursor-pointer
                    ${dragOver
                        ? 'border-[var(--accent)] bg-[var(--accent-subtle)] scale-[1.01]'
                        : 'border-[var(--border)] hover:border-[var(--border-hover)] bg-[var(--surface)]'
                    }
                `}
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
                <div className={`flex items-center justify-center size-12 rounded-full mb-3 transition-colors ${dragOver ? 'bg-[var(--accent)]/20' : 'bg-[var(--surface-raised)]'
                    }`}>
                    {uploading
                        ? <Loader2 className="size-6 text-[var(--accent)] animate-spin" />
                        : <Upload className="size-6 text-[var(--text-muted)]" />
                    }
                </div>
                <p className="text-sm text-[var(--text-primary)] font-medium">
                    {uploading ? t('documents.uploading') : t('documents.dropzone')}
                </p>
                <p className="text-xs text-[var(--text-muted)] mt-1">
                    {t('documents.dropzoneHint')}
                </p>
            </div>

            {/* Upload Error */}
            {uploadError && (
                <div className="flex items-start gap-2 px-4 py-3 mb-4 rounded-[var(--radius-md)] bg-[var(--error-subtle)] border border-[var(--error)]/20 text-[var(--error)] text-sm">
                    <span className="shrink-0 mt-0.5">⚠</span>
                    <span>{uploadError}</span>
                    <button
                        className="ml-auto shrink-0 opacity-60 hover:opacity-100 transition-opacity"
                        onClick={() => setUploadError(null)}
                    >
                        ✕
                    </button>
                </div>
            )}

            {/* Loading */}
            {isLoading && (
                <div className="flex items-center justify-center py-12 text-[var(--text-muted)]">
                    <Loader2 className="size-5 animate-spin mr-2" />
                    {t('documents.loadingDocuments')}
                </div>
            )}

            {/* Empty State */}
            {!isLoading && documents?.length === 0 && (
                <FadeIn>
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="flex items-center justify-center size-14 rounded-full bg-[var(--surface-raised)] mb-3">
                            <FileText className="size-6 text-[var(--text-muted)]" />
                        </div>
                        <p className="text-sm text-[var(--text-muted)]">
                            {t('documents.empty')}
                        </p>
                    </div>
                </FadeIn>
            )}

            {/* Document List */}
            {documents && documents.length > 0 && (
                <StaggerContainer className="space-y-2" itemCount={documents.length}>
                    {documents.map((doc) => (
                        <StaggerItem key={doc.id}>
                            <div className="flex items-center justify-between p-4 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-hover)] transition-colors group">
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="flex items-center justify-center size-9 rounded-[var(--radius-sm)] bg-[var(--surface-raised)] shrink-0">
                                        <FileText className="size-4 text-[var(--text-muted)]" />
                                    </div>
                                    <div className="min-w-0">
                                        <h3 className="text-sm font-medium text-[var(--text-primary)] truncate">
                                            {doc.title}
                                        </h3>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <Badge variant={STATUS_VARIANT[doc.parse_status] ?? 'secondary'}>
                                                {t(`documents.status.${doc.parse_status}` as Parameters<typeof t>[0])}
                                            </Badge>
                                            {doc.year && (
                                                <span className="text-xs text-[var(--text-muted)]">
                                                    ({doc.year})
                                                </span>
                                            )}
                                            {doc.doi && (
                                                <span className="text-xs text-[var(--text-muted)] truncate max-w-48">
                                                    {doc.doi}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                    {doc.parse_status === 'failed' && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => retryParse.mutate(doc.id)}
                                        >
                                            <RotateCcw className="size-3.5" />
                                            {t('common.retry')}
                                        </Button>
                                    )}
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-[var(--error)] hover:text-[var(--error)] hover:bg-[var(--error-subtle)]"
                                        onClick={() => deleteDocument.mutate(doc.id)}
                                    >
                                        <Trash2 className="size-3.5" />
                                        {t('common.delete')}
                                    </Button>
                                </div>
                            </div>
                        </StaggerItem>
                    ))}
                </StaggerContainer>
            )}
        </div>
    )
}
