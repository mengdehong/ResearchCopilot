/**
 * 英文翻译字典 — 同时也是翻译合约的类型源。
 * 所有其他语言的字典必须满足 TranslationDict 类型。
 */

export const en = {
    common: {
        save: 'Save',
        saved: '✓ Saved',
        cancel: 'Cancel',
        create: 'Create',
        delete: 'Delete',
        retry: 'Retry',
        loading: 'Loading...',
        approve: 'Approve',
        reject: 'Reject',
    },
    nav: {
        workspaces: 'Workspaces',
        settings: 'Settings',
    },
    workspace: {
        title: 'Workspaces',
        subtitle: 'Manage your research workspaces',
        newWorkspace: '+ New Workspace',
        createTitle: 'Create Workspace',
        creating: 'Creating...',
        loadingWorkspaces: 'Loading workspaces...',
        empty: 'No workspaces yet. Create one to get started!',
        created: 'Created {{date}}',
        deleteTitle: 'Delete workspace',
    },
    discipline: {
        computer_science: 'Computer Science',
        biology: 'Biology',
        physics: 'Physics',
        mathematics: 'Mathematics',
        chemistry: 'Chemistry',
        other: 'Other',
    },
    settings: {
        title: 'Settings',
        subtitle: 'Configure your Research Copilot preferences',
        language: 'Language',
        auth: 'Authentication',
        apiKeyLabel: 'API Key',
        apiKeyHint: 'Your API key is stored locally in the browser.',
        preferences: 'Preferences',
        defaultDiscipline: 'Default Discipline',
    },
    chat: {
        title: 'Chat',
        streaming: 'Streaming',
    },
    documents: {
        title: 'Documents',
        subtitle: 'Manage research documents in this workspace',
        uploading: 'Uploading...',
        dropzone: 'Drag & drop PDF files here, or click to upload',
        dropzoneHint: 'Supports PDF files up to 50MB',
        loadingDocuments: 'Loading documents...',
        empty: 'No documents yet. Upload PDFs to get started.',
    },
    hitl: {
        selectPapers: 'Select Papers',
        noPapers: 'No papers to select.',
        confirmSelection: 'Confirm Selection ({{count}})',
        confirmExecute: 'Confirm Code Execution',
        noCode: 'No code provided.',
        approveExecute: 'Approve & Execute',
        confirmFinalize: 'Confirm Finalization',
        noContent: 'No content to preview.',
        editInCanvas: 'Edit in Canvas',
        unknownAction: 'Unknown action: {{action}}',
    },
    status: {
        processing: 'Processing...',
        idle: 'Idle',
    },
} as const

/** 递归将对象中所有字面量字符串类型展宽为 string。 */
type Stringify<T> = T extends string
    ? string
    : { [K in keyof T]: Stringify<T[K]> }

export type TranslationDict = Stringify<typeof en>

