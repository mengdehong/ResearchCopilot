import { useState, useCallback, useRef, useEffect, type KeyboardEvent, type ChangeEvent } from 'react'
import { Send, Loader2, Paperclip, X, Mic, MicOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n/useTranslation'
import useVoiceInput from '@/hooks/useVoiceInput'

interface InputAreaProps {
    onSend: (message: string, files?: File[]) => void
    disabled: boolean
    threadId: string
}

export default function InputArea({ onSend, disabled }: InputAreaProps) {
    const [value, setValue] = useState('')
    const [files, setFiles] = useState<File[]>([])
    const fileInputRef = useRef<HTMLInputElement>(null)
    const { t } = useTranslation()

    // ─── Voice Input ───

    const handleTranscript = useCallback((text: string) => {
        setValue((prev) => (prev ? prev + ' ' + text : text))
    }, [])

    const voice = useVoiceInput(handleTranscript)

    const [displayTime, setDisplayTime] = useState('0:00')
    useEffect(() => {
        const mins = Math.floor(voice.elapsedSeconds / 60)
        const secs = voice.elapsedSeconds % 60
        setDisplayTime(`${mins}:${secs.toString().padStart(2, '0')}`)
    }, [voice.elapsedSeconds])

    const handleMicClick = useCallback(async () => {
        if (voice.status === 'recording') {
            voice.stopRecording()
        } else {
            await voice.startRecording()
        }
    }, [voice])

    const isRecording = voice.status === 'recording'
    const isTranscribing = voice.status === 'transcribing'

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
        <div className="shrink-0 px-4 py-4 pb-5 border-t border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-2xl z-20">
            {/* Recording indicator */}
            {isRecording && (
                <div className="flex items-center gap-2 mb-2 px-2 py-1.5 rounded-lg bg-[var(--error-subtle,rgba(239,68,68,0.1))]">
                    <span className="size-2 rounded-full bg-red-500 animate-[pulse-glow_2s_ease-in-out_infinite]" />
                    <span className="text-xs text-red-500 font-medium">
                        {t('chat.voice.recording')}
                    </span>
                    <span className="text-xs text-[var(--text-muted)] font-mono">{displayTime}</span>
                    {voice.interimText && (
                        <span className="text-xs text-[var(--text-secondary)] truncate max-w-[200px] italic">
                            {voice.interimText}
                        </span>
                    )}
                </div>
            )}

            {/* Transcribing indicator */}
            {isTranscribing && (
                <div className="flex items-center gap-2 mb-2 px-2 py-1.5 rounded-lg bg-[var(--accent-subtle)]">
                    <Loader2 className="size-3 animate-spin text-[var(--accent)]" />
                    <span className="text-xs text-[var(--accent)]">
                        {t('chat.voice.transcribing')}
                    </span>
                </div>
            )}

            {/* Voice error */}
            {voice.error && voice.status === 'error' && (
                <div className="flex items-center gap-2 mb-2 px-2 py-1.5 rounded-lg bg-[var(--error-subtle,rgba(239,68,68,0.1))]">
                    <span className="text-xs text-red-500">
                        {voice.error === 'mic-permission-denied'
                            ? t('chat.voice.micPermissionDenied')
                            : t('chat.voice.error')}
                    </span>
                </div>
            )}

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

                {/* Voice button */}
                <Button
                    size="icon"
                    variant="ghost"
                    onClick={handleMicClick}
                    disabled={disabled || isTranscribing}
                    aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
                    className={`shrink-0 transition-colors ${isRecording
                            ? 'text-red-500 hover:text-red-600 animate-[pulse-glow_2s_ease-in-out_infinite]'
                            : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                        }`}
                >
                    {isTranscribing ? (
                        <Loader2 className="size-4 animate-spin" />
                    ) : isRecording ? (
                        <MicOff className="size-4" />
                    ) : (
                        <Mic className="size-4" />
                    )}
                </Button>

                <div className="flex-1 relative">
                    <textarea
                        className="w-full resize-none rounded-3xl border border-[var(--border)] bg-[var(--background)] px-5 py-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-[3px] focus:ring-[var(--accent-subtle)] transition-all shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] focus:shadow-[var(--shadow-md)] disabled:opacity-50"
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
                    className="shrink-0 transition-all duration-200 active:scale-[0.85] rounded-full h-10 w-10 shadow-[var(--shadow-sm)]"
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
