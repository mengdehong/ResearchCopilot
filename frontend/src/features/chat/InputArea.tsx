import { useState, useCallback, useRef, type KeyboardEvent, type ChangeEvent } from 'react'
import { Send, Loader2, Paperclip, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface InputAreaProps {
    onSend: (message: string, files?: File[]) => void
    disabled: boolean
    threadId: string
}

export default function InputArea({ onSend, disabled }: InputAreaProps) {
    const [value, setValue] = useState('')
    const [files, setFiles] = useState<File[]>([])
    const fileInputRef = useRef<HTMLInputElement>(null)

    const handleSend = useCallback(() => {
        const trimmed = value.trim()
        if (!trimmed || disabled) return
        onSend(trimmed, files.length > 0 ? files : undefined)
        setValue('')
        setFiles([])
    }, [value, disabled, onSend, files])

    const handleKeyDown = useCallback(
        (e: KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
            }
        },
        [handleSend],
    )

    const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
        const selected = e.target.files
        if (!selected) return
        setFiles((prev) => [...prev, ...Array.from(selected)])
        // Reset input so the same file can be selected again
        e.target.value = ''
    }, [])

    const removeFile = useCallback((index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index))
    }, [])

    return (
        <div className="px-4 py-3 border-t border-[var(--border)] bg-[var(--surface)]">
            {/* File tags */}
            {files.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                    {files.map((file, i) => (
                        <span
                            key={`${file.name}-${i}`}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--surface-raised)] text-xs text-[var(--text-secondary)] border border-[var(--border)]"
                        >
                            <Paperclip className="size-3" />
                            <span className="max-w-[120px] truncate">{file.name}</span>
                            <button
                                onClick={() => removeFile(i)}
                                className="hover:text-[var(--error)] transition-colors cursor-pointer"
                                aria-label={`Remove ${file.name}`}
                            >
                                <X className="size-3" />
                            </button>
                        </span>
                    ))}
                </div>
            )}

            <div className="flex items-end gap-2">
                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={handleFileSelect}
                    multiple
                    accept=".pdf,.txt,.md,.csv,.json,.py,.ipynb,.tex,.bib"
                />

                {/* Attach button */}
                <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={disabled}
                    aria-label="Attach files"
                    className="shrink-0 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                    <Paperclip className="size-4" />
                </Button>

                <div className="flex-1 relative">
                    <textarea
                        className="w-full resize-none rounded-2xl border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-[3px] focus:ring-[var(--accent-subtle)] transition-all disabled:opacity-50"
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
