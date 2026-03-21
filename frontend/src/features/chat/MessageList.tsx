import { useEffect, useRef } from 'react'
import type { Message } from '@/types'
import { Bot, User } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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

    return (
        <div className={`relative flex gap-3 px-6 py-3 ${isAssistant ? 'bg-[var(--surface)]' : ''}`}>
            {/* Accent line for assistant messages */}
            {isAssistant && (
                <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-[var(--accent)]" />
            )}

            <Avatar className="size-7 shrink-0 mt-0.5">
                <AvatarFallback className={
                    isAssistant
                        ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                        : 'bg-[var(--surface-raised)] text-[var(--text-secondary)]'
                }>
                    {isAssistant ? <Bot className="size-3.5" /> : <User className="size-3.5" />}
                </AvatarFallback>
            </Avatar>

            <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-[var(--text-muted)] mb-1">
                    {isAssistant ? 'Assistant' : 'You'}
                </div>
                <div className="text-sm text-[var(--text-primary)] leading-relaxed prose-sm">
                    <AcademicMarkdown content={message.content} />
                </div>
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
        <div className="relative flex gap-3 px-6 py-3 bg-[var(--surface)]">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-[var(--accent)]" />

            <Avatar className="size-7 shrink-0 mt-0.5">
                <AvatarFallback className="bg-[var(--accent-subtle)] text-[var(--accent)]">
                    <Bot className="size-3.5" />
                </AvatarFallback>
            </Avatar>

            <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-[var(--text-muted)] mb-1">
                    Assistant
                </div>
                <div className="text-sm text-[var(--text-primary)] leading-relaxed">
                    <AcademicMarkdown content={content} />
                    <span className="inline-block w-0.5 h-4 ml-0.5 bg-[var(--accent)] animate-blink align-text-bottom" />
                </div>
            </div>
        </div>
    )
}
