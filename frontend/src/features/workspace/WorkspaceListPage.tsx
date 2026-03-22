import { useNavigate } from 'react-router-dom'
import { useWorkspaces, useCreateWorkspace, useDeleteWorkspace } from '@/hooks/useWorkspaces'
import { useTranslation } from '@/i18n/useTranslation'
import { DISCIPLINES } from '@/types'
import { useState } from 'react'
import { Plus, Trash2, BookOpen, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { StaggerContainer, StaggerItem, FadeIn } from '@/components/shared/MotionWrappers'
import { SkeletonCard } from '@/components/ui/skeleton'

/** Discipline gradient colors for card accent bars */
const DISCIPLINE_GRADIENTS: Record<string, string> = {
    computer_science: 'from-blue-500 to-cyan-400',
    biology: 'from-green-500 to-emerald-400',
    physics: 'from-violet-500 to-purple-400',
    mathematics: 'from-amber-500 to-orange-400',
    chemistry: 'from-rose-500 to-pink-400',
    other: 'from-slate-500 to-gray-400',
}

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
                    setDiscipline('computer_science')
                    setShowCreate(false)
                },
            },
        )
    }

    return (
        <div className="h-full overflow-auto p-8 md:p-12">
            {/* Header */}
            <div className="flex items-center justify-between mb-10">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                        {t('workspace.title')}
                    </h1>
                    <p className="text-sm text-[var(--text-secondary)] mt-1">
                        {t('workspace.subtitle')}
                    </p>
                </div>
                <Button onClick={() => setShowCreate(true)}>
                    <Plus className="size-4" />
                    {t('workspace.newWorkspace')}
                </Button>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    <SkeletonCard />
                    <SkeletonCard />
                    <SkeletonCard />
                </div>
            )}

            {/* Empty State */}
            {!isLoading && workspaces?.length === 0 && (
                <FadeIn>
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                        <div className="flex items-center justify-center size-16 rounded-full bg-[var(--accent-subtle)] mb-4">
                            <BookOpen className="size-7 text-[var(--accent)]" />
                        </div>
                        <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                            {t('workspace.empty')}
                        </h3>
                        <p className="text-sm text-[var(--text-secondary)] mb-6 max-w-md">
                            Create your first workspace to start organizing your research.
                        </p>
                        <Button onClick={() => setShowCreate(true)}>
                            <Plus className="size-4" />
                            {t('workspace.newWorkspace')}
                        </Button>
                    </div>
                </FadeIn>
            )}

            {/* Card Grid */}
            {workspaces && workspaces.length > 0 && (
                <StaggerContainer
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
                    itemCount={workspaces.length}
                >
                    {workspaces.map((ws) => (
                        <StaggerItem key={ws.id}>
                            <div
                                className="group relative flex items-stretch rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] hover:border-transparent hover:-translate-y-1 hover:shadow-[var(--shadow-lg)] transition-all duration-300 ease-out cursor-pointer overflow-hidden"
                                onClick={() => navigate(`/workspace/${ws.id}`)}
                            >
                                {/* Discipline gradient accent bar */}
                                <div
                                    className={`w-1.5 shrink-0 bg-gradient-to-b ${DISCIPLINE_GRADIENTS[ws.discipline] ?? DISCIPLINE_GRADIENTS.other}`}
                                />

                                <div className="flex-1 p-4 min-w-0">
                                    <div className="flex items-start justify-between mb-2">
                                        <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate pr-2">
                                            {ws.name}
                                        </h3>
                                        <button
                                            className="opacity-0 group-hover:opacity-100 p-1 rounded-[var(--radius-sm)] text-[var(--text-muted)] hover:text-[var(--error)] hover:bg-[var(--error-subtle)] transition-all cursor-pointer"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                deleteWorkspace.mutate(ws.id)
                                            }}
                                            title={t('workspace.deleteTitle')}
                                        >
                                            <Trash2 className="size-3.5" />
                                        </button>
                                    </div>

                                    <Badge variant="secondary" className="mb-2">
                                        {t(`discipline.${ws.discipline as 'computer_science' | 'biology' | 'physics' | 'mathematics' | 'chemistry' | 'other'}`)}
                                    </Badge>

                                    <p className="text-xs text-[var(--text-muted)]">
                                        {t('workspace.created', {
                                            date: new Date(ws.created_at).toLocaleDateString(),
                                        })}
                                    </p>
                                </div>
                            </div>
                        </StaggerItem>
                    ))}

                </StaggerContainer>
            )}

            {/* Create Dialog */}
            <Dialog open={showCreate} onOpenChange={setShowCreate}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t('workspace.createTitle')}</DialogTitle>
                        <DialogDescription>
                            Create a new research workspace to organize your papers and notes.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex flex-col gap-4 py-2">
                        <Input
                            placeholder="Workspace name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            autoFocus
                        />
                        <Select value={discipline} onValueChange={setDiscipline}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {DISCIPLINES.map((d) => (
                                    <SelectItem key={d} value={d}>
                                        {t(`discipline.${d}`)}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowCreate(false)}>
                            {t('common.cancel')}
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={!name.trim() || createWorkspace.isPending}
                        >
                            {createWorkspace.isPending && (
                                <Loader2 className="size-4 animate-spin" />
                            )}
                            {createWorkspace.isPending
                                ? t('workspace.creating')
                                : t('common.create')}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
