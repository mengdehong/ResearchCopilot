/* ─── Auth ─── */
export interface TokenPayload {
    sub: string
    exp: number
}

export interface UserInfo {
    id: string
    email: string
    display_name: string
}

/* ─── Workspace ─── */
export interface Workspace {
    id: string
    name: string
    discipline: string
    owner_id: string
    is_deleted: boolean
    created_at: string
    updated_at: string
}

export interface WorkspaceCreate {
    name: string
    discipline?: string
}

export interface WorkspaceSummary {
    workspace_id: string
    name: string
    document_count: number
    doc_status_counts: {
        uploading: number
        pending: number
        parsing: number
        completed: number
        failed: number
    }
}

/* ─── Document ─── */
export interface DocumentMeta {
    id: string
    workspace_id: string
    title: string
    file_path: string
    parse_status: string
    source: string
    doi: string | null
    abstract_text: string | null
    year: number | null
    include_appendix: boolean
    created_at: string
    updated_at: string
}

export interface DocumentCreate {
    title: string
    file_path: string
    workspace_id: string
    doi?: string
    abstract_text?: string
    year?: number
    source?: string
    include_appendix?: boolean
}

export interface DocumentStatus {
    id: string
    parse_status: string
    updated_at: string
}

/* ─── Agent ─── */
export interface RunRequest {
    message: string
    editor_content?: string
    attachment_ids?: string[]
}

export interface RunEvent {
    event_type: string
    data: Record<string, unknown>
}

export interface InterruptResponse {
    action: string
    feedback?: string
    payload?: Record<string, unknown>
}

export interface RunResult {
    run_id: string
    thread_id: string
    status: string
    stream_url: string
}

export interface ThreadInfo {
    thread_id: string
    title: string
    status: string
    updated_at?: string
    workspace_id?: string
    langgraph_thread_id?: string
}

export interface ThreadDetail {
    thread_id: string
    title: string
    status: string
    active_run_id: string | null
}

/* ─── Editor ─── */
export interface DraftSave {
    content: string
}

export interface DraftLoad {
    thread_id: string
    content: string
    updated_at: string
}

/* ─── Chat/SSE ─── */
export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
    id: string
    role: MessageRole
    content: string
    timestamp: string
    cotNodes?: CotNodeSummary[]
}

export interface CotNodeSummary {
    name: string
    status: string
    duration_ms?: number
}

export interface CoTNode {
    id: string
    name: string
    startTime: number
    endTime: number | null
    children: CoTNode[]
    status: 'running' | 'completed' | 'error'
}

export type HITLAction = 'select_papers' | 'confirm_execute' | 'confirm_finalize' | 'wait_for_ingestion'

export interface InterruptData {
    action: HITLAction
    run_id: string
    thread_id: string
    payload: Record<string, unknown>
}

export type CanvasTab = 'editor' | 'pdf' | 'sandbox' | 'research'

export interface PdfHighlight {
    document_id: string
    page: number
    bbox: number[]
    text_snippet: string
}

export interface SandboxImage {
    name: string
    /** base64-encoded image content (no data-URI prefix). */
    data: string
}

export interface SandboxResult {
    code: string
    stdout: string
    stderr: string
    exit_code: number
    duration_ms: number
    artifacts: string[]
    images: SandboxImage[]
}

/* ─── Research Blocks ─── */
export interface ResearchBlock {
    content: string
    workflow: string
}

/* ─── Constants ─── */
export const DISCIPLINES = [
    'computer_science',
    'biology',
    'physics',
    'mathematics',
    'chemistry',
    'other',
] as const

export type Discipline = (typeof DISCIPLINES)[number]
