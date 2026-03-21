import { useState, useCallback, type KeyboardEvent } from 'react'
import { Send, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface InputAreaProps {
    onSend: (message: string) => void
    disabled: boolean
    threadId: string
}

export default function InputArea({ onSend, disabled }: InputAreaProps) {
    const [value, setValue] = useState('')

    const handleSend = useCallback(() => {
        const trimmed = value.trim()
        if (!trimmed || disabled) return
        onSend(trimmed)
        setValue('')
    }, [value, disabled, onSend])

    const handleKeyDown = useCallback(
        (e: KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
            }
        },
        [handleSend],
    )

    return (
        <div className="px-4 py-3 border-t border-[var(--border)] bg-[var(--surface)]">
            <div className="flex items-end gap-2">
                <div className="flex-1 relative">
                    <textarea
                        className="w-full resize-none rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-[3px] focus:ring-[var(--accent-subtle)] transition-all disabled:opacity-50"
                        placeholder="Type your research question..."
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={disabled}
                        rows={1}
                    />
                </div>
                <Button
                    size="icon"
                    onClick={handleSend}
                    disabled={disabled || !value.trim()}
                    aria-label="Send message"
                    className="shrink-0"
                >
                    {disabled ? (
                        <Loader2 className="size-4 animate-spin" />
                    ) : (
                        <Send className="size-4" />
                    )}
                </Button>
            </div>
            <p className="text-[10px] text-[var(--text-muted)] mt-1.5 text-center">
                Press <kbd className="px-1 py-0.5 rounded bg-[var(--surface-raised)] text-[var(--text-secondary)] font-mono text-[9px]">Enter</kbd> to send,{' '}
                <kbd className="px-1 py-0.5 rounded bg-[var(--surface-raised)] text-[var(--text-secondary)] font-mono text-[9px]">Shift+Enter</kbd> for new line
            </p>
        </div>
    )
}
