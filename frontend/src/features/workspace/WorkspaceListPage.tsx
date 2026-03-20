import { useNavigate } from 'react-router-dom'
import { useWorkspaces, useCreateWorkspace, useDeleteWorkspace } from '@/hooks/useWorkspaces'
import { useTranslation } from '@/i18n/useTranslation'
import { DISCIPLINES } from '@/types'
import { useState } from 'react'
import './WorkspaceListPage.css'

export default function WorkspaceListPage() {
    const navigate = useNavigate()
    const { data: workspaces, isLoading } = useWorkspaces()
    const createWorkspace = useCreateWorkspace()
    const deleteWorkspace = useDeleteWorkspace()
    const { t } = useTranslation()

    const [showCreate, setShowCreate] = useState(false)
    const [name, setName] = useState('')
    const [discipline, setDiscipline] = useState('computer_science')

    const handleCreate = () => {
        if (!name.trim()) return
        createWorkspace.mutate(
            { name: name.trim(), discipline },
            {
                onSuccess: () => {
                    setName('')
                    setShowCreate(false)
                },
            },
        )
    }

    return (
        <div className="workspace-list-page">
            <div className="workspace-list-page__header">
                <div>
                    <h1>{t('workspace.title')}</h1>
                    <p className="text-muted">{t('workspace.subtitle')}</p>
                </div>
                <button
                    className="btn btn--primary"
                    onClick={() => setShowCreate(true)}
                >
                    {t('workspace.newWorkspace')}
                </button>
            </div>

            {showCreate && (
                <div className="card workspace-create-card">
                    <h3>{t('workspace.createTitle')}</h3>
                    <div className="workspace-create-card__form">
                        <input
                            className="workspace-input"
                            placeholder="Workspace name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            autoFocus
                        />
                        <select
                            className="workspace-select"
                            value={discipline}
                            onChange={(e) => setDiscipline(e.target.value)}
                        >
                            {DISCIPLINES.map((d) => (
                                <option key={d} value={d}>
                                    {t(`discipline.${d}`)}
                                </option>
                            ))}
                        </select>
                        <div className="workspace-create-card__actions">
                            <button className="btn btn--ghost" onClick={() => setShowCreate(false)}>
                                {t('common.cancel')}
                            </button>
                            <button
                                className="btn btn--primary"
                                onClick={handleCreate}
                                disabled={!name.trim() || createWorkspace.isPending}
                            >
                                {createWorkspace.isPending ? t('workspace.creating') : t('common.create')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isLoading && (
                <div className="workspace-list-page__loading">{t('workspace.loadingWorkspaces')}</div>
            )}

            <div className="workspace-grid">
                {workspaces?.map((ws) => (
                    <div
                        key={ws.id}
                        className="card card--interactive workspace-card"
                        onClick={() => navigate(`/workspace/${ws.id}`)}
                    >
                        <div className="workspace-card__top">
                            <div className="workspace-card__icon">📚</div>
                            <button
                                className="btn btn--ghost btn--sm workspace-card__delete"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    deleteWorkspace.mutate(ws.id)
                                }}
                                title={t('workspace.deleteTitle')}
                            >
                                ×
                            </button>
                        </div>
                        <h3 className="workspace-card__name">{ws.name}</h3>
                        <span className="badge badge--accent">
                            {t(`discipline.${ws.discipline as 'computer_science' | 'biology' | 'physics' | 'mathematics' | 'chemistry' | 'other'}`)}
                        </span>
                        <p className="workspace-card__date text-muted">
                            {t('workspace.created', { date: new Date(ws.created_at).toLocaleDateString() })}
                        </p>
                    </div>
                ))}

                {!isLoading && workspaces?.length === 0 && (
                    <div className="workspace-list-page__empty">
                        <p>{t('workspace.empty')}</p>
                    </div>
                )}
            </div>
        </div>
    )
}
