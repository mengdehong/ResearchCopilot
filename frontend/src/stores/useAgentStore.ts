import { create } from 'zustand'
import type { Message, CoTNode, InterruptData, RunEvent, PdfHighlight, SandboxResult } from '@/types'
import { createLogger } from '@/lib/logger'

const log = createLogger('Store')

interface AgentState {
    messages: Message[]
    cotTree: CoTNode[]
    interrupt: InterruptData | null
    isStreaming: boolean
    currentNode: string | null
    /** 流式 token 累积缓冲。token 事件写入，assistant_message 事件消费后清空。
     *  当前 EditorTab 直接通过 inserContent 流式写入，generatedContent 仅用于
     *  assistant_message 回退（无 supervisor AIMessage 时）。 */
    generatedContent: string
    contentBlocks: { content: string; workflow: string }[]
    activePdf: PdfHighlight | null
    sandboxResult: SandboxResult | null

    addMessage: (msg: Message) => void
    loadMessages: (msgs: Message[]) => void
    handleSSEEvent: (event: RunEvent) => void
    clearInterrupt: () => void
    reset: () => void
    resetRunState: () => void
    setStreaming: (streaming: boolean) => void
    setActivePdf: (pdf: PdfHighlight | null) => void
    consumeContentBlock: () => { content: string; workflow: string } | null
}

export const useAgentStore = create<AgentState>((set, get) => ({
    messages: [],
    cotTree: [],
    interrupt: null,
    isStreaming: false,
    currentNode: null,
    generatedContent: '',
    contentBlocks: [],
    activePdf: null,
    sandboxResult: null,

    addMessage: (msg) =>
        set((state) => ({ messages: [...state.messages, msg] })),

    loadMessages: (msgs) => set({ messages: msgs }),

    setActivePdf: (pdf) => set({ activePdf: pdf }),

    handleSSEEvent: (event) => {
        const { event_type, data } = event
        log.debug('event', { event_type })

        switch (event_type) {
            // NOTE: token 事件目前仅用于 generatedContent 累积，供 assistant_message
            // 回退发送时使用。EditorTab 通过独立的 generatedContent selector 流式渲染。
            case 'token':
                set((state) => ({
                    generatedContent: state.generatedContent + String(data.content ?? ''),
                }))
                break

            case 'node_start': {
                const nodeName = String(data.node_name ?? '')
                const newNode: CoTNode = {
                    id: String(data.node_id ?? crypto.randomUUID()),
                    name: nodeName,
                    startTime: Date.now(),
                    endTime: null,
                    children: [],
                    status: 'running',
                }
                set((state) => ({
                    currentNode: nodeName,
                    isStreaming: true,
                    cotTree: [...state.cotTree, newNode],
                }))
                break
            }

            case 'node_end': {
                const endNodeId = String(data.node_id ?? '')
                const endNodeName = String(data.node_name ?? '')
                set((state) => ({
                    currentNode: null,
                    cotTree: state.cotTree.map((n) => {
                        const matchById = endNodeId && n.id === endNodeId
                        const matchByName = !endNodeId && n.name === endNodeName && n.status === 'running'
                        return matchById || matchByName
                            ? { ...n, endTime: Date.now(), status: 'completed' as const }
                            : n
                    }),
                }))
                break
            }

            case 'interrupt': {
                const interrupt: InterruptData = {
                    action: data.action as InterruptData['action'],
                    run_id: String(data.run_id ?? ''),
                    thread_id: String(data.thread_id ?? ''),
                    payload: data as Record<string, unknown>,
                }
                set({ interrupt, isStreaming: false })
                break
            }

            case 'assistant_message': {
                const msg: Message = {
                    id: crypto.randomUUID(),
                    role: 'assistant',
                    content: get().generatedContent || String(data.content ?? ''),
                    timestamp: new Date().toISOString(),
                }
                set((state) => ({
                    messages: [...state.messages, msg],
                    generatedContent: '',
                }))
                break
            }

            case 'error': {
                log.error('agent error', { message: data.message })
                const errMsg: Message = {
                    id: crypto.randomUUID(),
                    role: 'system',
                    content: String(data.message ?? 'Unknown error'),
                    timestamp: new Date().toISOString(),
                }
                set((state) => ({
                    messages: [...state.messages, errMsg],
                }))
                break
            }

            case 'content_block': {
                const content = String(data.content ?? '')
                const workflow = String(data.workflow ?? '')
                if (content) {
                    set((state) => ({
                        contentBlocks: [...state.contentBlocks, { content, workflow }],
                    }))
                }
                break
            }

            case 'run_end':
                set({ isStreaming: false, currentNode: null })
                break

            case 'pdf_highlight': {
                const highlight = {
                    document_id: String(data.document_id ?? ''),
                    page: Number(data.page ?? 1),
                    bbox: Array.isArray(data.bbox) ? data.bbox.map(Number) : [],
                    text_snippet: String(data.text_snippet ?? ''),
                }
                set({ activePdf: highlight })
                // Also optionally set layout store tab to 'pdf', but usually done in CanvasPanel or here
                break
            }

            case 'sandbox_result': {
                const result = {
                    code: String(data.code ?? ''),
                    stdout: String(data.stdout ?? ''),
                    stderr: String(data.stderr ?? ''),
                    exit_code: Number(data.exit_code ?? 0),
                    duration_ms: Number(data.duration_ms ?? 0),
                    artifacts: Array.isArray(data.artifacts) ? data.artifacts.map(String) : [],
                }
                set({ sandboxResult: result })
                break
            }

            default:
                log.warn('unknown event', { event_type })
                break
        }
    },

    clearInterrupt: () => set({ interrupt: null }),

    reset: () =>
        set({
            messages: [],
            cotTree: [],
            interrupt: null,
            isStreaming: false,
            currentNode: null,
            generatedContent: '',
            contentBlocks: [],
            activePdf: null,
            sandboxResult: null,
        }),

    resetRunState: () =>
        set({
            cotTree: [],
            interrupt: null,
            isStreaming: false,
            currentNode: null,
            generatedContent: '',
        }),

    setStreaming: (streaming) => set({ isStreaming: streaming }),

    consumeContentBlock: () => {
        const blocks = get().contentBlocks
        if (blocks.length === 0) return null
        const [first, ...rest] = blocks
        set({ contentBlocks: rest })
        return first
    },
}))
