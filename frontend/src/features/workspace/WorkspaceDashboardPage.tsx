import { useNavigate, useParams } from 'react-router-dom'
import {
    ArrowLeft,
    BookOpen,
    MessageSquare,
    Zap,
    Plus,
    ExternalLink,
    FileText,
    CheckCircle2,
    AlertCircle,
    Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useWorkspaceSummary } from '@/hooks/useWorkspaces'
import { useThreads } from '@/hooks/useThreads'
import { useDocuments } from '@/hooks/useDocuments'
import type { ThreadInfo, DocumentMeta } from '@/types'

const DISCIPLINE_COLORS: Record<string, string> = {
    computer_science: 'from-violet-500 to-indigo-600',
    biology: 'from-emerald-500 to-teal-600',
    physics: 'from-blue-500 to-cyan-600',
    mathematics: 'from-amber-500 to-orange-600',
    chemistry: 'from-pink-500 to-rose-600',
    other: 'from-slate-500 to-zinc-600',
}

interface StatCardProps {
    icon: React.ReactNode
    label: string
    value: number | string
    sublabel?: string
    color?: string
}

function StatCard({ icon, label, value, sublabel, color = 'var(--accent)' }: StatCardProps) {
    return (
        <div className="flex items-center gap-4 p-5 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)]">
            <div
                className="flex items-center justify-center size-12 rounded-[var(--radius-md)] shrink-0"
                style={{ background: `color-mix(in srgb, ${color} 15%, transparent)` }}
            >
                <span style={{ color }}>{icon}</span>
            </div>
            <div>
                <p className="text-xs text-[var(--text-muted)] mb-0.5">{label}</p>
                <p className="text-2xl font-bold text-[var(--text-primary)]">{value}</p>
                {sublabel && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{sublabel}</p>}
            </div>
        </div>
    )
}

function ThreadRow({ thread, workspaceId }: { thread: ThreadInfo; workspaceId: string }) {
    const navigate = useNavigate()
    const isActive = thread.status === 'running'

    return (
        <button
            className="w-full flex items-center gap-3 px-4 py-3 rounded-[var(--radius-md)] hover:bg-[var(--surface-hover)] transition-colors text-left group cursor-pointer"
            onClick={() => navigate(`/workspace/${workspaceId}/chat?thread=${thread.thread_id}`)}
        >
            <div
                className={`size-2 rounded-full shrink-0 ${isActive ? 'bg-[var(--accent)] animate-pulse' : 'bg-[var(--text-muted)]'}`}
            />
            <span className="flex-1 text-sm text-[var(--text-primary)] truncate">{thread.title}</span>
            {thread.updated_at && (
                <span className="text-xs text-[var(--text-muted)] shrink-0">
                    {new Date(thread.updated_at).toLocaleDateString()}
                </span>
            )}
            <ExternalLink className="size-3.5 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
        </button>
    )
}

function DocStatusIcon({ status }: { status: string }) {
    if (status === 'completed') return <CheckCircle2 className="size-3.5 text-[var(--success)]" />
    if (status === 'failed') return <AlertCircle className="size-3.5 text-[var(--error)]" />
    return <Loader2 className="size-3.5 text-[var(--accent)] animate-spin" />
}

function DocumentRow({ doc }: { doc: DocumentMeta }) {
    return (
        <div className="flex items-center gap-3 px-4 py-3 rounded-[var(--radius-md)] hover:bg-[var(--surface-hover)] transition-colors">
            <DocStatusIcon status={doc.parse_status} />
            <span className="flex-1 text-sm text-[var(--text-primary)] truncate">{doc.title}</span>
            <Badge variant="secondary" className="text-[10px] shrink-0">
                {doc.parse_status}
            </Badge>
        </div>
    )
}

export default function WorkspaceDashboardPage() {
    const { id: workspaceId = '' } = useParams<{ id: string }>()
    const navigate = useNavigate()

    const { data: summary, isLoading: summaryLoading } = useWorkspaceSummary(workspaceId)
    const { data: threads = [], isLoading: threadsLoading } = useThreads(workspaceId, 10)
    const { data: documents = [], isLoading: docsLoading } = useDocuments(workspaceId)



    const completedDocs = documents.filter((d) => d.parse_status === 'completed').length
    const processingDocs = documents.filter((d) =>
        ['uploading', 'pending', 'parsing'].includes(d.parse_status),
    ).length

    return (
        <div className="h-full overflow-auto">
            {/* Header */}
            <div className={`bg-gradient-to-r ${DISCIPLINE_COLORS['computer_science']} px-8 py-8`}>
                <button
                    className="flex items-center gap-1.5 text-white/70 hover:text-white text-sm mb-4 transition-colors cursor-pointer"
                    onClick={() => navigate('/workspaces')}
                >
                    <ArrowLeft className="size-4" />
                    所有工作区
                </button>
                <div className="flex items-end justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white">
                            {summaryLoading ? '...' : (summary?.name ?? 'Workspace')}
                        </h1>
                        <p className="text-white/70 text-sm mt-1">研究工作区概览</p>
                    </div>
                    <Button
                        className="bg-white/20 hover:bg-white/30 text-white border-white/30"
                        variant="outline"
                        onClick={() => navigate(`/workspace/${workspaceId}/chat`)}
                    >
                        <MessageSquare className="size-4" />
                        进入工作台
                    </Button>
                </div>
            </div>

            <div className="p-8 space-y-8 max-w-5xl">
                {/* Stat Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <StatCard
                        icon={<BookOpen className="size-5" />}
                        label="文献总数"
                        value={summaryLoading ? '...' : (summary?.document_count ?? 0)}
                        sublabel={`${completedDocs} 已就绪  ${processingDocs > 0 ? `· ${processingDocs} 处理中` : ''}`}
                        color="var(--accent)"
                    />
                    <StatCard
                        icon={<MessageSquare className="size-5" />}
                        label="研究对话"
                        value={summaryLoading ? '...' : (summary?.thread_count ?? 0)}
                        color="#10b981"
                    />
                    <StatCard
                        icon={<Zap className="size-5" />}
                        label="工作流运行"
                        value={threads.filter((t) => t.status === 'running').length}
                        sublabel="当前活跃"
                        color="#f59e0b"
                    />
                </div>

                {/* Thread List */}
                <section>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-semibold text-[var(--text-primary)]">近期对话</h2>
                        <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs h-7"
                            onClick={() => navigate(`/workspace/${workspaceId}/chat`)}
                        >
                            <Plus className="size-3.5" />
                            新建对话
                        </Button>
                    </div>
                    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)]">
                        {threadsLoading ? (
                            <div className="flex items-center justify-center py-8 text-[var(--text-muted)]">
                                <Loader2 className="size-5 animate-spin" />
                            </div>
                        ) : threads.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-10 text-center">
                                <MessageSquare className="size-8 text-[var(--text-muted)] mb-2" />
                                <p className="text-sm text-[var(--text-secondary)]">还没有对话</p>
                                <Button
                                    className="mt-3"
                                    size="sm"
                                    onClick={() => navigate(`/workspace/${workspaceId}/chat`)}
                                >
                                    开始第一次对话
                                </Button>
                            </div>
                        ) : (
                            threads.map((t) => (
                                <ThreadRow key={t.thread_id} thread={t} workspaceId={workspaceId} />
                            ))
                        )}
                    </div>
                </section>

                {/* Document List */}
                <section>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-semibold text-[var(--text-primary)]">文献库</h2>
                        <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs h-7"
                            onClick={() => navigate(`/workspace/${workspaceId}/documents`)}
                        >
                            管理文献
                        </Button>
                    </div>
                    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)]">
                        {docsLoading ? (
                            <div className="flex items-center justify-center py-8 text-[var(--text-muted)]">
                                <Loader2 className="size-5 animate-spin" />
                            </div>
                        ) : documents.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-10 text-center">
                                <FileText className="size-8 text-[var(--text-muted)] mb-2" />
                                <p className="text-sm text-[var(--text-secondary)]">还没有文献</p>
                            </div>
                        ) : (
                            documents
                                .slice(0, 8)
                                .map((d) => <DocumentRow key={d.id} doc={d} />)
                        )}
                        {documents.length > 8 && (
                            <button
                                className="w-full py-3 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors cursor-pointer"
                                onClick={() => navigate(`/workspace/${workspaceId}/documents`)}
                            >
                                查看全部 {documents.length} 篇文献 →
                            </button>
                        )}
                    </div>
                </section>
            </div>
        </div>
    )
}
