import { useEffect, useRef, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { useAgentStore } from '@/stores/useAgentStore'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { useDraft, useSaveDraft } from '@/hooks/useDraft'
import './EditorTab.css'

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
                class: 'tiptap-editor',
            },
        },
    })

    // Load draft when available
    useEffect(() => {
        if (draft?.content && editor) {
            editor.commands.setContent(draft.content)
        }
    }, [draft, editor])

    // Append agent-generated content to editor
    useEffect(() => {
        if (!editor || !generatedContent) return
        if (generatedContent === prevGeneratedRef.current) return

        const newContent = generatedContent.slice(prevGeneratedRef.current.length)
        if (newContent) {
            editor.commands.insertContent(newContent)
        }
        prevGeneratedRef.current = generatedContent
    }, [editor, generatedContent])

    // Auto-save with debounce
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
        <div className="editor-tab">
            {editor && (
                <div className="editor-tab__toolbar">
                    <button
                        className={`toolbar-btn ${editor.isActive('bold') ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleBold().run()}
                        title="Bold"
                    >
                        <strong>B</strong>
                    </button>
                    <button
                        className={`toolbar-btn ${editor.isActive('italic') ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleItalic().run()}
                        title="Italic"
                    >
                        <em>I</em>
                    </button>
                    <button
                        className={`toolbar-btn ${editor.isActive('heading', { level: 1 }) ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                        title="Heading 1"
                    >
                        H1
                    </button>
                    <button
                        className={`toolbar-btn ${editor.isActive('heading', { level: 2 }) ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                        title="Heading 2"
                    >
                        H2
                    </button>
                    <div className="toolbar-divider" />
                    <button
                        className={`toolbar-btn ${editor.isActive('bulletList') ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleBulletList().run()}
                        title="Bullet List"
                    >
                        •
                    </button>
                    <button
                        className={`toolbar-btn ${editor.isActive('orderedList') ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleOrderedList().run()}
                        title="Ordered List"
                    >
                        1.
                    </button>
                    <button
                        className={`toolbar-btn ${editor.isActive('blockquote') ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleBlockquote().run()}
                        title="Blockquote"
                    >
                        &quot;
                    </button>
                    <button
                        className={`toolbar-btn ${editor.isActive('codeBlock') ? 'toolbar-btn--active' : ''}`}
                        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
                        title="Code Block"
                    >
                        {'</>'}
                    </button>
                    <div className="toolbar-divider" />
                    <button
                        className="toolbar-btn"
                        onClick={handleSave}
                        title="Save draft"
                        disabled={!threadId}
                    >
                        💾
                    </button>
                    {saveDraft.isPending && (
                        <span className="toolbar-status">Saving...</span>
                    )}
                </div>
            )}
            <div className="editor-tab__content">
                <EditorContent editor={editor} />
            </div>
        </div>
    )
}
