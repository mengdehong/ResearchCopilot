import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

interface PasswordInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string
    error?: string
}

export function PasswordInput({ label, error, ...props }: PasswordInputProps) {
    const [showPassword, setShowPassword] = useState(false)

    return (
        <div className="space-y-1.5">
            {label && (
                <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]/60 ml-1">
                    {label}
                </label>
            )}
            <div className="relative">
                <input
                    type={showPassword ? 'text' : 'password'}
                    className="w-full px-5 py-3.5 rounded-2xl bg-[var(--surface)] border border-[var(--border)] focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/5 outline-none transition-all placeholder:text-[var(--text-muted)]/30 text-[var(--text-primary)] text-sm"
                    {...props}
                />
                <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]/30 hover:text-[var(--text-secondary)] transition-colors"
                    tabIndex={-1}
                >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
            </div>
            {error && <span className="text-sm text-[var(--error)] ml-1">{error}</span>}
        </div>
    )
}
