import { useEffect, useRef, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { useAgentStore } from '@/stores/useAgentStore'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { useDraft, useSaveDraft } from '@/hooks/useDraft'
import { Bold, Italic, Heading1, Heading2, List, ListOrdered, Quote, Code2, Save, Loader2 } from 'lucide-react'
import './tiptap-editor.css'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'

interface EditorTabProps {
    threadId: string
}

export default function EditorTab({ threadId }: EditorTabProps) {
    const { data: draft } = useDraft(threadId)
    const saveDraft = useSaveDraft()
    const generatedContent = useAgentStore((s) => s.generatedContent)
    const setSaveStatus = useLayoutStore((s) => s.setSaveStatus)
    const prevGeneratedRef = useRef('')
    const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const editor = useEditor({
        extensions: [StarterKit],
        content: '<p>Start writing your research document here...</p>',
        editorProps: {
            attributes: {
                class: 'outline-none min-h-full px-8 py-6 text-sm leading-relaxed text-[var(--text-primary)]',
            },
        },
    })

    useEffect(() => {
        if (draft?.content && editor) {
            editor.commands.setContent(draft.content)
        }
    }, [draft, editor])

    useEffect(() => {
        if (!editor || !generatedContent) return
        if (generatedContent === prevGeneratedRef.current) return

        const newContent = generatedContent.slice(prevGeneratedRef.current.length)
        if (newContent) {
            editor.commands.insertContent(newContent)
        }
        prevGeneratedRef.current = generatedContent
    }, [editor, generatedContent])

    const handleSave = useCallback(() => {
        if (!editor || !threadId) return
        const content = editor.getHTML()
        setSaveStatus('saving')
        saveDraft.mutate(
            { threadId, content },
            {
                onSuccess: () => {
                    setSaveStatus('saved')
                    if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
                    savedTimerRef.current = setTimeout(() => setSaveStatus('idle'), 2000)
                },
                onError: () => {
                    setSaveStatus('idle')
                },
            },
        )
    }, [editor, threadId, saveDraft, setSaveStatus])

    useEffect(() => {
        if (!editor) return

        const debouncedSave = () => {
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
            saveTimerRef.current = setTimeout(handleSave, 2000)
        }

        editor.on('update', debouncedSave)
        return () => {
            editor.off('update', debouncedSave)
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
            if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
        }
    }, [editor, handleSave])

    return (
        <div className="flex flex-col h-full">
            {/* Toolbar */}
            {editor && (
                <div className="flex items-center gap-0.5 px-3 py-1.5 border-b border-[var(--border)] bg-[var(--surface-raised)]">
                    <ToolbarGroup>
                        <ToolbarButton
                            icon={<Bold className="size-3.5" />}
                            label="Bold"
                            active={editor.isActive('bold')}
                            onClick={() => editor.chain().focus().toggleBold().run()}
                        />
                        <ToolbarButton
                            icon={<Italic className="size-3.5" />}
                            label="Italic"
                            active={editor.isActive('italic')}
                            onClick={() => editor.chain().focus().toggleItalic().run()}
                        />
                    </ToolbarGroup>

                    <div className="w-px h-5 bg-[var(--border)] mx-1" />

                    <ToolbarGroup>
                        <ToolbarButton
                            icon={<Heading1 className="size-3.5" />}
                            label="Heading 1"
                            active={editor.isActive('heading', { level: 1 })}
                            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                        />
                        <ToolbarButton
                            icon={<Heading2 className="size-3.5" />}
                            label="Heading 2"
                            active={editor.isActive('heading', { level: 2 })}
                            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                        />
                    </ToolbarGroup>

                    <div className="w-px h-5 bg-[var(--border)] mx-1" />

                    <ToolbarGroup>
                        <ToolbarButton
                            icon={<List className="size-3.5" />}
                            label="Bullet List"
                            active={editor.isActive('bulletList')}
                            onClick={() => editor.chain().focus().toggleBulletList().run()}
                        />
                        <ToolbarButton
                            icon={<ListOrdered className="size-3.5" />}
                            label="Ordered List"
                            active={editor.isActive('orderedList')}
                            onClick={() => editor.chain().focus().toggleOrderedList().run()}
                        />
                        <ToolbarButton
                            icon={<Quote className="size-3.5" />}
                            label="Blockquote"
                            active={editor.isActive('blockquote')}
                            onClick={() => editor.chain().focus().toggleBlockquote().run()}
                        />
                        <ToolbarButton
                            icon={<Code2 className="size-3.5" />}
                            label="Code Block"
                            active={editor.isActive('codeBlock')}
                            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
                        />
                    </ToolbarGroup>

                    <div className="w-px h-5 bg-[var(--border)] mx-1" />

                    <ToolbarButton
                        icon={saveDraft.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                        label="Save draft"
                        onClick={handleSave}
                        disabled={!threadId}
                    />
                </div>
            )}

            {/* Editor */}
            <div className="flex-1 overflow-auto">
                <EditorContent editor={editor} />
            </div>
        </div>
    )
}

/* ─── Toolbar Helpers ─── */
function ToolbarGroup({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center gap-0.5">{children}</div>
}

interface ToolbarButtonProps {
    readonly icon: React.ReactNode
    readonly label: string
    readonly active?: boolean
    readonly disabled?: boolean
    readonly onClick: () => void
}

function ToolbarButton({ icon, label, active = false, disabled = false, onClick }: ToolbarButtonProps) {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <button
                    className={`
                        flex items-center justify-center size-7 rounded-[var(--radius-sm)] transition-colors cursor-pointer
                        ${active
                            ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                            : 'text-[var(--text-muted)] hover:bg-[var(--surface)] hover:text-[var(--text-primary)]'
                        }
                        ${disabled ? 'opacity-50 pointer-events-none' : ''}
                    `}
                    onClick={onClick}
                    disabled={disabled}
                >
                    {icon}
                </button>
            </TooltipTrigger>
            <TooltipContent>{label}</TooltipContent>
        </Tooltip>
    )
}
