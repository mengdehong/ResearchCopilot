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

            case 'node_start':
                set({
                    currentNode: String(data.node_name ?? ''),
                    isStreaming: true,
                })
                break

            case 'node_end':
                set({ currentNode: null })
                break

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
