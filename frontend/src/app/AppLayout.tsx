import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { getToken } from '@/lib/api'
import { useTranslation } from '@/i18n/useTranslation'
import { useEffect } from 'react'
import './AppLayout.css'

export default function AppLayout() {
    const navigate = useNavigate()
    const token = getToken()
    const { t } = useTranslation()

    useEffect(() => {
        if (!token) {
            // MVP: no login page, just stay. In production would redirect to /login
        }
    }, [token, navigate])

    return (
        <div className="app-layout">
            <nav className="global-nav">
                <div className="nav-top">
                    <NavLink to="/workspaces" className="nav-logo" aria-label="Home">
                        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                            <rect width="28" height="28" rx="8" fill="var(--color-accent)" />
                            <text x="14" y="19" textAnchor="middle" fill="#fff" fontSize="14" fontWeight="700">R</text>
                        </svg>
                    </NavLink>

                    <NavLink to="/workspaces" className="nav-item" title={t('nav.workspaces')}>
                        <svg className="icon" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M2 4.5A2.5 2.5 0 014.5 2h11A2.5 2.5 0 0118 4.5v11a2.5 2.5 0 01-2.5 2.5h-11A2.5 2.5 0 012 15.5v-11zM4.5 4a.5.5 0 00-.5.5v11a.5.5 0 00.5.5h11a.5.5 0 00.5-.5v-11a.5.5 0 00-.5-.5h-11z" />
                        </svg>
                    </NavLink>
                </div>

                <div className="nav-bottom">
                    <NavLink to="/settings" className="nav-item" title={t('nav.settings')}>
                        <svg className="icon" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M8.34 1.804A1 1 0 019.32 1h1.36a1 1 0 01.98.804l.295 1.473c.497.179.971.417 1.413.706l1.373-.612a1 1 0 011.17.353l.68 1.178a1 1 0 01-.192 1.157l-1.078.86a6.046 6.046 0 010 1.411l1.078.862a1 1 0 01.192 1.157l-.68 1.178a1 1 0 01-1.17.353l-1.373-.612a5.96 5.96 0 01-1.413.706l-.295 1.473a1 1 0 01-.98.804H9.32a1 1 0 01-.98-.804l-.295-1.473a5.96 5.96 0 01-1.413-.706l-1.373.612a1 1 0 01-1.17-.353l-.68-1.178a1 1 0 01.192-1.157l1.078-.862a6.046 6.046 0 010-1.411l-1.078-.86a1 1 0 01-.192-1.157l.68-1.178a1 1 0 011.17-.353l1.373.612a5.96 5.96 0 011.413-.706l.295-1.473zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
                        </svg>
                    </NavLink>
                </div>
            </nav>

            <main className="app-content">
                <Outlet />
            </main>
        </div>
    )
}
