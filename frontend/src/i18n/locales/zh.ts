/**
 * 中文翻译字典 — 必须满足 TranslationDict 类型约束。
 * 缺少任何 key 将导致 TypeScript 编译错误。
 */

import type { TranslationDict } from './en'

export const zh: TranslationDict = {
    common: {
        save: '保存',
        saved: '✓ 已保存',
        cancel: '取消',
        create: '创建',
        delete: '删除',
        retry: '重试',
        loading: '加载中...',
        approve: '批准',
        reject: '拒绝',
    },
    nav: {
        workspaces: '工作区',
        settings: '设置',
    },
    workspace: {
        title: '工作区',
        subtitle: '管理你的研究工作区',
        newWorkspace: '+ 新建工作区',
        createTitle: '创建工作区',
        creating: '创建中...',
        loadingWorkspaces: '加载工作区...',
        empty: '暂无工作区，创建一个开始吧！',
        created: '创建于 {{date}}',
        deleteTitle: '删除工作区',
    },
    discipline: {
        computer_science: '计算机科学',
        biology: '生物学',
        physics: '物理学',
        mathematics: '数学',
        chemistry: '化学',
        other: '其他',
    },
    settings: {
        title: '设置',
        subtitle: '配置你的 Research Copilot 偏好',
        language: '语言',
        auth: '认证',
        apiKeyLabel: 'API 密钥',
        apiKeyHint: '你的 API 密钥存储在浏览器本地。',
        preferences: '偏好设置',
        defaultDiscipline: '默认学科',
    },
    chat: {
        title: '对话',
        streaming: '流式传输中',
    },
    documents: {
        title: '文档',
        subtitle: '管理此工作区中的研究文档',
        uploading: '上传中...',
        dropzone: '拖拽 PDF 文件到此处，或点击上传',
        dropzoneHint: '支持最大 50MB 的 PDF 文件',
        loadingDocuments: '加载文档...',
        empty: '暂无文档，上传 PDF 开始吧。',
    },
    hitl: {
        selectPapers: '选择论文',
        noPapers: '暂无论文可选。',
        confirmSelection: '确认选择 ({{count}})',
        confirmExecute: '确认代码执行',
        noCode: '未提供代码。',
        approveExecute: '批准并执行',
        confirmFinalize: '确认定稿',
        noContent: '暂无内容可预览。',
        editInCanvas: '在画布中编辑',
        unknownAction: '未知操作: {{action}}',
    },
    status: {
        processing: '处理中...',
        idle: '空闲',
    },
}
