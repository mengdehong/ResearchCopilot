import { useEffect, useRef } from 'react'
import type { Message } from '@/types'
import './MessageList.css'

interface MessageListProps {
    messages: Message[]
    streamingContent?: string
}

export default function MessageList({ messages, streamingContent }: MessageListProps) {
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, streamingContent])

    return (
        <div className="message-list">
            {messages.length === 0 && !streamingContent && (
                <div className="message-list__empty">
                    <div className="message-list__empty-icon">💬</div>
                    <p>Start a conversation to begin your research.</p>
                </div>
            )}

            {messages.map((msg) => (
                <div
                    key={msg.id}
                    className={`message message--${msg.role}`}
                >
                    <div className="message__avatar">
                        {msg.role === 'user' ? '👤' : '🤖'}
                    </div>
                    <div className="message__content">
                        <div className="message__role">
                            {msg.role === 'user' ? 'You' : 'Assistant'}
                        </div>
                        <div className="message__text">{msg.content}</div>
                    </div>
                </div>
            ))}

            {streamingContent && (
                <div className="message message--assistant message--streaming">
                    <div className="message__avatar">🤖</div>
                    <div className="message__content">
                        <div className="message__role">Assistant</div>
                        <div className="message__text">
                            {streamingContent}
                            <span className="message__cursor" />
                        </div>
                    </div>
                </div>
            )}

            <div ref={bottomRef} />
        </div>
    )
}
