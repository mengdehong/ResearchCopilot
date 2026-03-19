# Phase 7: Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 实现 React + TypeScript 前端：项目脚手架、路由、核心页面（Chat/Canvas、文档管理、设置）、SSE 实时通信。

**Architecture:** Vite + React SPA，Zustand 全局状态，React Query 服务端缓存，TipTap 富文本编辑器。

**前置条件：** Phase 5（BFF API 可调用）

**对应设计文档：**
- [前端架构设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-frontend-architecture-design.md) — 全文

---

## 文件结构

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── routes/
│   ├── stores/                # Zustand stores
│   ├── hooks/                 # React Query hooks
│   ├── components/
│   │   ├── chat/              # 对话面板
│   │   ├── canvas/            # TipTap 编辑器
│   │   ├── sidebar/           # 侧边栏（Workspace/Thread 列表）
│   │   └── common/            # 通用组件
│   ├── services/              # API 客户端
│   └── types/                 # TypeScript 类型
```

---

## Task 1: 前端脚手架

- [ ] **Step 1: Vite + React + TypeScript 初始化**
- [ ] **Step 2: 安装核心依赖** — zustand, @tanstack/react-query, react-router-dom
- [ ] **Step 3: 设计系统（CSS 变量 + 主题）**
- [ ] **Step 4: Commit**

---

## Task 2: 路由和布局

- [ ] **Step 1: React Router 配置** — `/workspace/:id`, `/settings`
- [ ] **Step 2: 主布局组件** — Sidebar + Main（Chat/Canvas 分栏）
- [ ] **Step 3: Commit**

---

## Task 3: Zustand 状态管理

- [ ] **Step 1: workspaceStore** — 当前 workspace、thread 列表
- [ ] **Step 2: chatStore** — 消息列表、发送状态
- [ ] **Step 3: canvasStore** — 编辑器内容
- [ ] **Step 4: Commit**

---

## Task 4: API 客户端和 React Query Hooks

- [ ] **Step 1: API 客户端** — axios/fetch 封装，JWT 自动注入
- [ ] **Step 2: React Query hooks** — useWorkspaces, useThreads, useDocuments
- [ ] **Step 3: SSE 连接管理** — EventSource 封装 + 自动重连
- [ ] **Step 4: Commit**

---

## Task 5: 核心页面

- [ ] **Step 1: Chat 面板** — 消息列表 + 输入框 + SSE 流式渲染
- [ ] **Step 2: Canvas 面板** — TipTap 编辑器 + 工具栏
- [ ] **Step 3: HITL 交互** — 代码确认弹窗、报告预览确认
- [ ] **Step 4: 文档管理页** — 上传 + 解析状态显示
- [ ] **Step 5: Commit**

---

## 验证清单

| 检查项     | 命令               | 期望结果              |
| ---------- | ------------------ | --------------------- |
| 开发服务器 | `npm run dev`      | localhost:5173 可访问 |
| 构建       | `npm run build`    | 无错误                |
| TypeScript | `npx tsc --noEmit` | 0 errors              |
| Lint       | `npx eslint src/`  | 0 errors              |

---

**Phase 7 完成标志：** 前端可运行 + 核心页面渲染 + SSE 消息流通 → 可进入 Phase 8。
