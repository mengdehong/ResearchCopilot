import { useState, useCallback, type KeyboardEvent } from 'react'
import './InputArea.css'

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
        <div className="input-area">
            <div className="input-area__wrapper">
                <textarea
                    className="input-area__textarea"
                    placeholder="Type your research question..."
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={disabled}
                    rows={1}
                />
                <button
                    className="input-area__send btn btn--primary"
                    onClick={handleSend}
                    disabled={disabled || !value.trim()}
                    aria-label="Send message"
                >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M1.724 1.053a.5.5 0 01.627-.186l12 5.5a.5.5 0 010 .916l-12 5.5a.5.5 0 01-.697-.557L2.88 8.513a.5.5 0 01.47-.413l4.15-.276a.25.25 0 000-.498L3.35 7.05a.5.5 0 01-.47-.413L1.654 2.923a.5.5 0 01.07-.37z" />
                    </svg>
                </button>
            </div>
            <p className="input-area__hint">
                Press <kbd>Enter</kbd> to send, <kbd>Shift+Enter</kbd> for new line
            </p>
        </div>
    )
}
