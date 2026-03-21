import { Outlet, NavLink, useParams, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { LayoutGrid, Settings, Sun, Moon, PanelLeftClose, PanelLeftOpen, MessageSquare } from 'lucide-react'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { useTheme } from '@/hooks/useTheme'
import { useTranslation } from '@/i18n/useTranslation'
import { useThreads } from '@/hooks/useThreads'

import {
    Tooltip,
    TooltipTrigger,
    TooltipContent,
} from '@/components/ui/tooltip'

const SIDEBAR_SPRING = { type: 'spring' as const, damping: 25, stiffness: 300 }
const COLLAPSED_WIDTH = 56
const EXPANDED_WIDTH = 240

export default function AppLayout() {
    const { t } = useTranslation()
    const navigate = useNavigate()
    const location = useLocation()
    const { id: workspaceId } = useParams<{ id: string }>()
    const navExpanded = useLayoutStore((s) => s.navExpanded)
    const toggleNav = useLayoutStore((s) => s.toggleNav)
    const { resolvedTheme, setTheme } = useTheme()

    return (
        <div className="flex h-screen w-screen overflow-hidden bg-[var(--background)]">
            {/* ─── Sidebar ─── */}
            <motion.nav
                className="relative flex flex-col h-screen border-r border-[var(--border)] bg-[var(--surface)] overflow-hidden select-none"
                animate={{ width: navExpanded ? EXPANDED_WIDTH : COLLAPSED_WIDTH }}
                transition={SIDEBAR_SPRING}
            >
                {/* Top: Logo + Nav Items */}
                <div className="flex flex-col items-center gap-1 pt-3 px-2">
                    {/* Logo */}
                    <NavLink
                        to="/workspaces"
                        className="flex items-center gap-2.5 w-full px-2 py-2 mb-2 rounded-[var(--radius-sm)] hover:bg-[var(--surface-raised)] transition-colors"
                    >
                        <div className="flex items-center justify-center w-8 h-8 shrink-0 rounded-[var(--radius-sm)] bg-[var(--accent)] text-white text-sm font-bold">
                            R
                        </div>
                        <AnimatePresence>
                            {navExpanded && (
                                <motion.span
                                    className="text-sm font-semibold text-[var(--text-primary)] whitespace-nowrap overflow-hidden"
                                    initial={{ opacity: 0, width: 0 }}
                                    animate={{ opacity: 1, width: 'auto' }}
                                    exit={{ opacity: 0, width: 0 }}
                                    transition={{ duration: 0.15 }}
                                >
                                    Research Copilot
                                </motion.span>
                            )}
                        </AnimatePresence>
                    </NavLink>

                    {/* Expand/collapse toggle */}
                    <SidebarButton
                        icon={navExpanded
                            ? <PanelLeftClose className="size-4" />
                            : <PanelLeftOpen className="size-4" />
                        }
                        label={navExpanded ? t('nav.collapse') : t('nav.expand')}
                        expanded={navExpanded}
                        onClick={toggleNav}
                    />

                    {/* Workspaces */}
                    <SidebarButton
                        icon={<LayoutGrid className="size-4" />}
                        label={t('nav.workspaces')}
                        expanded={navExpanded}
                        onClick={() => navigate('/workspaces')}
                        active={!workspaceId && location.pathname.includes('/workspaces')}
                    />
                </div>

                {/* Middle: Thread History (only when expanded + in workspace) */}
                <div className="flex-1 overflow-hidden">
                    <AnimatePresence>
                        {navExpanded && workspaceId && (
                            <motion.div
                                className="px-2 pt-3 h-full flex flex-col"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.15 }}
                            >
                                <div className="px-2 pb-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                                    Threads
                                </div>
                                <ThreadList workspaceId={workspaceId} />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Bottom: Theme + Settings */}
                <div className="flex flex-col items-center gap-1 pb-3 px-2 border-t border-[var(--border)] pt-2">
                    {/* Theme Switch */}
                    <SidebarButton
                        icon={resolvedTheme === 'dark'
                            ? <Sun className="size-4" />
                            : <Moon className="size-4" />
                        }
                        label={resolvedTheme === 'dark' ? t('settings.lightMode') : t('settings.darkMode')}
                        expanded={navExpanded}
                        onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
                    />

                    {/* Settings */}
                    <SidebarButton
                        icon={<Settings className="size-4" />}
                        label={t('nav.settings')}
                        expanded={navExpanded}
                        onClick={() => navigate('/settings')}
                        active={location.pathname.includes('/settings')}
                    />


                </div>
            </motion.nav>

            {/* ─── Main Content ─── */}
            <main className="flex-1 overflow-auto h-screen bg-[var(--background)]">
                <Outlet />
            </main>
        </div>
    )
}

/* ─── SidebarButton ─── */
interface SidebarButtonProps {
    readonly icon: React.ReactNode
    readonly label: string
    readonly expanded: boolean
    readonly onClick: () => void
    readonly active?: boolean
}

function SidebarButton({ icon, label, expanded, onClick, active = false }: SidebarButtonProps) {
    const button = (
        <button
            onClick={onClick}
            className={`
                flex items-center gap-2.5 w-full px-2.5 py-2 rounded-[var(--radius-sm)]
                text-sm transition-colors cursor-pointer
                ${active
                    ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--surface-raised)] hover:text-[var(--text-primary)]'
                }
            `}
        >
            <span className="shrink-0">{icon}</span>
            <AnimatePresence>
                {expanded && (
                    <motion.span
                        className="whitespace-nowrap overflow-hidden"
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: 'auto' }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.15 }}
                    >
                        {label}
                    </motion.span>
                )}
            </AnimatePresence>
        </button>
    )

    if (!expanded) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{button}</TooltipTrigger>
                <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
        )
    }

    return button
}

/* ─── ThreadList ─── */
interface ThreadListProps {
    readonly workspaceId: string
}

function ThreadList({ workspaceId }: ThreadListProps) {
    const { data: threads } = useThreads(workspaceId)
    const navigate = useNavigate()

    if (!threads?.length) {
        return (
            <div className="px-2 py-4 text-xs text-[var(--text-muted)] text-center">
                No threads yet
            </div>
        )
    }

    return (
        <div className="flex-1 overflow-y-auto scrollbar-hide space-y-0.5">
            {threads.map((thread) => (
                <button
                    key={thread.thread_id}
                    onClick={() => navigate(`/workspace/${workspaceId}?thread=${thread.thread_id}`)}
                    className="flex items-center gap-2 w-full px-2 py-1.5 rounded-[var(--radius-sm)] text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-raised)] hover:text-[var(--text-primary)] transition-colors text-left cursor-pointer"
                >
                    <MessageSquare className="size-3.5 shrink-0" />
                    <span className="truncate">{thread.title}</span>
                </button>
            ))}
        </div>
    )
}
