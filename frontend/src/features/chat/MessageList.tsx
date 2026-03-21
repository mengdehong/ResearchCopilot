import { useEffect, useRef } from 'react'
import type { Message } from '@/types'
import { Bot } from 'lucide-react'
import { SlideUp } from '@/components/shared/MotionWrappers'
import AcademicMarkdown from '@/components/shared/AcademicMarkdown'

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
        <div className="flex flex-col gap-0 py-4">
            {messages.length === 0 && !streamingContent && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="flex items-center justify-center size-12 rounded-full bg-[var(--accent-subtle)] mb-3">
                        <Bot className="size-6 text-[var(--accent)]" />
                    </div>
                    <p className="text-sm text-[var(--text-muted)]">
                        Start a conversation to begin your research.
                    </p>
                </div>
            )}

            {messages.map((msg) => (
                <SlideUp key={msg.id}>
                    <MessageBubble message={msg} />
                </SlideUp>
            ))}

            {streamingContent && (
                <StreamingMessage content={streamingContent} />
            )}

            <div ref={bottomRef} />
        </div>
    )
}

/* ─── MessageBubble ─── */
interface MessageBubbleProps {
    readonly message: Message
}

function MessageBubble({ message }: MessageBubbleProps) {
    const isAssistant = message.role === 'assistant'
    const isSystem = message.role === 'system'

    if (isSystem) {
        return (
            <div className="px-6 py-2">
                <div className="text-center text-xs text-[var(--text-muted)] bg-[var(--warning-subtle)] rounded-[var(--radius-sm)] py-2 px-4">
                    {message.content}
                </div>
            </div>
        )
    }

    // User message: right-aligned bubble
    if (!isAssistant) {
        return (
            <div className="flex justify-end px-6 py-3">
                <div className="max-w-[85%] rounded-3xl rounded-br-md bg-[var(--surface-raised)] border border-[var(--border)] px-5 py-3.5 text-[var(--text-primary)] text-[15px] leading-relaxed shadow-[var(--shadow-sm)]">
                    <AcademicMarkdown content={message.content} />
                </div>
            </div>
        )
    }

    // Assistant message: left-aligned, no bubble, no avatar
    return (
        <div className="px-6 py-4">
            <div className="text-[15px] text-[var(--text-primary)] leading-relaxed prose-sm max-w-none">
                <AcademicMarkdown content={message.content} />
            </div>
        </div>
    )
}

/* ─── Streaming Message ─── */
interface StreamingMessageProps {
    readonly content: string
}

function StreamingMessage({ content }: StreamingMessageProps) {
    return (
        <div className="px-6 py-3">
            <div className="text-sm text-[var(--text-primary)] leading-relaxed">
                <AcademicMarkdown content={content} />
                <span className="inline-block w-0.5 h-4 ml-0.5 bg-[var(--accent)] animate-blink align-text-bottom" />
            </div>
        </div>
    )
}
