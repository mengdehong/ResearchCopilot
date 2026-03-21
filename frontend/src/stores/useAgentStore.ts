import { create } from 'zustand'
import type { Message, CoTNode, InterruptData, RunEvent } from '@/types'

interface AgentState {
    messages: Message[]
    cotTree: CoTNode[]
    interrupt: InterruptData | null
    isStreaming: boolean
    currentNode: string | null
    generatedContent: string

    addMessage: (msg: Message) => void
    handleSSEEvent: (event: RunEvent) => void
    clearInterrupt: () => void
    reset: () => void
    setStreaming: (streaming: boolean) => void
}

export const useAgentStore = create<AgentState>((set, get) => ({
    messages: [],
    cotTree: [],
    interrupt: null,
    isStreaming: false,
    currentNode: null,
    generatedContent: '',

    addMessage: (msg) =>
        set((state) => ({ messages: [...state.messages, msg] })),

    handleSSEEvent: (event) => {
        const { event_type, data } = event

        switch (event_type) {
            case 'token':
                set((state) => ({
                    generatedContent: state.generatedContent + (data.content ?? ''),
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
                const endNodeName = String(data.node_name ?? '')
                set((state) => ({
                    currentNode: null,
                    cotTree: state.cotTree.map((n) =>
                        n.name === endNodeName && n.status === 'running'
                            ? { ...n, endTime: Date.now(), status: 'completed' as const }
                            : n
                    ),
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

            case 'run_end':
                set({ isStreaming: false, currentNode: null })
                break

            default:
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
        }),

    setStreaming: (streaming) => set({ isStreaming: streaming }),
}))
