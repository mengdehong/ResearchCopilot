import { useEffect, useRef, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import { TextSelection } from '@tiptap/pm/state'
import StarterKit from '@tiptap/starter-kit'
import MathExtension from '@aarkue/tiptap-math-extension'
import 'katex/dist/katex.min.css'
import { useAgentStore } from '@/stores/useAgentStore'
import { useLayoutStore } from '@/stores/useLayoutStore'
import { useDraft, useSaveDraft } from '@/hooks/useDraft'
import { Bold, Italic, Heading1, Heading2, Heading3, List, ListOrdered, Quote, Code2, Sigma, Save, Loader2 } from 'lucide-react'
import './tiptap-editor.css'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Extension } from '@tiptap/react'
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight'
import { createLowlight, common } from 'lowlight'
import 'highlight.js/styles/github-dark.css' // Or any suitable theme

const lowlight = createLowlight(common)

import type { EditorView } from '@tiptap/pm/view'
import type { Node as PmNode } from '@tiptap/pm/model'

function unpackMathNode(view: EditorView, node: PmNode, nodePos: number): void {
    const { tr } = view.state
    const latex = (node.attrs as Record<string, string>).latex || ''
    const isDisplay = (node.attrs as Record<string, string>).display === 'yes'
    const delimiter = isDisplay ? '$$' : '$'

    tr.insertText(`${delimiter}${latex}${delimiter}`, nodePos, nodePos + node.nodeSize)
    const newStart = nodePos + delimiter.length
    const newEnd = newStart + latex.length
    tr.setSelection(TextSelection.create(tr.doc, newStart, newEnd))
    view.dispatch(tr)
}

const MathShortcuts = Extension.create({
    name: 'mathShortcuts',
    addKeyboardShortcuts() {
        return {
            Enter: () => {
                const { state } = this.editor
                const { selection } = state
                const { $from, empty } = selection

                if (!empty) return false

                const textBefore = $from.parent.textContent

                // Match block math $$...$$ anywhere in the paragraph
                const matchBlock = textBefore.match(/\$\$(?!\s)(.*?(?<!\\))\$\$/)
                if (matchBlock) {
                    return this.editor.chain()
                        .deleteRange({ from: $from.start(), to: $from.end() })
                        .insertContent({
                            type: 'inlineMath',
                            attrs: { latex: matchBlock[1], display: 'yes', evaluate: 'no' },
                        })
                        .command(({ tr, dispatch }) => {
                            if (dispatch) tr.split(tr.selection.from)
                            return true
                        })
                        .run()
                }

                // Match inline math $...$ anywhere in the paragraph
                const matchInline = textBefore.match(/(?<!\$)\$(?![\s$])((?:[^$\\]|\\\$|\\)+?(?<![\s\\]))\$(?!\$)/)
                if (matchInline) {
                    return this.editor.chain()
                        .deleteRange({ from: $from.start(), to: $from.end() })
                        .insertContent({
                            type: 'inlineMath',
                            attrs: { latex: matchInline[1], display: 'no', evaluate: 'no' },
                        })
                        .command(({ tr, dispatch }) => {
                            if (dispatch) tr.split(tr.selection.from)
                            return true
                        })
                        .run()
                }

                // 如果段落中只有 $$，将其替换为公式块占位符
                if (textBefore.trim() === '$$' && $from.parent.type.name === 'paragraph') {
                    return this.editor.chain()
                        .deleteRange({ from: $from.start(), to: $from.end() })
                        .insertContent({
                            type: 'inlineMath',
                            attrs: { latex: '\\square', display: 'yes', evaluate: 'no' },
                        })
                        .run()
                }
                return false
            },
        }
    },
})

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
    const lastUnpackedParaRef = useRef<number | null>(null)

    const editor = useEditor({
        extensions: [
            StarterKit.configure({
                codeBlock: false,
            }),
            CodeBlockLowlight.configure({
                lowlight,
            }),
            MathExtension.configure({ addInlineMath: true }),
            MathShortcuts,
        ],
        content: '<p>Start writing your research document here...</p>',
        editorProps: {
            attributes: {
                class: 'outline-none min-h-full px-8 py-6 text-sm leading-relaxed text-[var(--text-primary)]',
            },
            handleClickOn(view, _pos, node, nodePos) {
                if (node.type.name === 'inlineMath') {
                    unpackMathNode(view, node, nodePos)
                    // Track which paragraph was unpacked
                    const $pos = view.state.doc.resolve(nodePos)
                    lastUnpackedParaRef.current = $pos.before($pos.depth)
                    return true
                }
                return false
            }
        },
        onSelectionUpdate({ editor: ed, transaction }) {
            // Only auto-unpack/repack on pure cursor moves (no doc changes)
            if (transaction.docChanged) return

            const { $from, empty } = ed.state.selection
            if (!empty) return

            const currentParaPos = $from.before($from.depth)

            // --- Repack logic: if cursor left the unpacked paragraph, repack it ---
            if (lastUnpackedParaRef.current !== null && currentParaPos !== lastUnpackedParaRef.current) {
                const prevParaPos = lastUnpackedParaRef.current
                lastUnpackedParaRef.current = null
                try {
                    const $prev = ed.state.doc.resolve(prevParaPos + 1)
                    const prevPara = $prev.parent
                    if (prevPara.type.name === 'paragraph' && prevPara.isTextblock) {
                        const text = prevPara.textContent
                        const blockMatch = text.match(/\$\$(?!\s)(.*?(?<!\\))\$\$/)
                        const inlineMatch = text.match(/(?<!\$)\$(?![\s$])((?:[^$\\]|\\\$|\\)+?(?<![\s\\]))\$(?!\$)/)
                        const match = blockMatch || inlineMatch
                        if (match) {
                            const isBlock = !!blockMatch
                            const latex = match[1]
                            const paraStart = prevParaPos + 1
                            const paraEnd = paraStart + prevPara.content.size
                            ed.chain()
                                .deleteRange({ from: paraStart, to: paraEnd })
                                .insertContentAt(paraStart, {
                                    type: 'inlineMath',
                                    attrs: { latex, display: isBlock ? 'yes' : 'no', evaluate: 'no' },
                                })
                                .run()
                            return
                        }
                    }
                } catch {
                    // Position may be invalid if doc changed, ignore
                }
            }

            // --- Unpack logic: if cursor is next to a math node, unpack it ---
            if ($from.nodeBefore?.type.name === 'inlineMath') {
                const nodePos = $from.pos - $from.nodeBefore.nodeSize
                unpackMathNode(ed.view, $from.nodeBefore, nodePos)
                lastUnpackedParaRef.current = currentParaPos
                return
            }
            if ($from.nodeAfter?.type.name === 'inlineMath') {
                unpackMathNode(ed.view, $from.nodeAfter, $from.pos)
                lastUnpackedParaRef.current = currentParaPos
            }
        },
        onBlur({ editor: ed }) {
            // When editor loses focus, repack any unpacked paragraph
            if (lastUnpackedParaRef.current !== null) {
                const prevParaPos = lastUnpackedParaRef.current
                lastUnpackedParaRef.current = null
                try {
                    const $prev = ed.state.doc.resolve(prevParaPos + 1)
                    const prevPara = $prev.parent
                    if (prevPara.type.name === 'paragraph' && prevPara.isTextblock) {
                        const text = prevPara.textContent
                        const blockMatch = text.match(/\$\$(?!\s)(.*?(?<!\\))\$\$/)
                        const inlineMatch = text.match(/(?<!\$)\$(?![\s$])((?:[^$\\]|\\\$|\\)+?(?<![\s\\]))\$(?!\$)/)
                        const match = blockMatch || inlineMatch
                        if (match) {
                            const isBlock = !!blockMatch
                            const latex = match[1]
                            const paraStart = prevParaPos + 1
                            const paraEnd = paraStart + prevPara.content.size
                            ed.chain()
                                .deleteRange({ from: paraStart, to: paraEnd })
                                .insertContentAt(paraStart, {
                                    type: 'inlineMath',
                                    attrs: { latex, display: isBlock ? 'yes' : 'no', evaluate: 'no' },
                                })
                                .run()
                        }
                    }
                } catch {
                    // ignore
                }
            }
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
                <div className="flex items-center flex-wrap gap-1 px-4 py-2 border-b border-[var(--border)] bg-gradient-to-br from-[var(--surface)] to-[var(--surface-raised)] shadow-[var(--shadow-sm)] sticky top-0 z-10">
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
                        <ToolbarButton
                            icon={<Heading3 className="size-3.5" />}
                            label="Heading 3"
                            active={editor.isActive('heading', { level: 3 })}
                            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
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
                        <ToolbarButton
                            icon={<Sigma className="size-3.5" />}
                            label="Math Formula ($$...$$)"
                            onClick={() => editor.chain().focus().insertContent({ type: 'inlineMath', attrs: { latex: '\\square', display: 'yes', evaluate: 'no' } }).run()}
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
