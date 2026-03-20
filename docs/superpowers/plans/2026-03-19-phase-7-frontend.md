# Phase 7: Frontend — 细化实施计划

> React + TypeScript SPA：Chat/Canvas 双栏工作区、SSE 实时通信、HITL 交互、文献管理。

## 设计决策

### 1. 包管理器
pnpm。

### 2. UI 组件库
shadcn/ui + Radix UI 原语。按需手动添加组件。

### 3. 认证前端
简单 API Key + localStorage Bearer Token（与后端 JWT mock 对齐）。

### 4. TipTap MVP 范围
- ✅ 基础格式（粗/斜/标题/列表/引用/代码块）
- ✅ Markdown 快捷输入
- ✅ KaTeX 公式渲染（只读）
- ❌ 图片拖拽上传（MVP 不做）
- ❌ 协作光标（后续迭代）

---

## Task 1: 前端脚手架

### 命令

```bash
pnpm create vite@latest ./ --template react-ts
pnpm add zustand @tanstack/react-query react-router-dom @tiptap/react @tiptap/starter-kit
pnpm add -D @types/react @types/react-dom eslint prettier
```

### 文件产出

| 文件                              | 说明                                    |
| --------------------------------- | --------------------------------------- |
| `frontend/vite.config.ts`         | Vite 配置（proxy → backend:8000）       |
| `frontend/src/app/App.tsx`        | 根组件                                  |
| `frontend/src/app/RootLayout.tsx` | Provider 注入层（QueryClient + Router） |
| `frontend/src/index.css`          | CSS 变量 + 设计 token + 暗色主题        |

### CSS 设计系统

```css
:root {
  --color-bg-primary: #0f0f13;
  --color-bg-secondary: #1a1a24;
  --color-bg-tertiary: #252533;
  --color-text-primary: #e4e4ee;
  --color-text-secondary: #9494a8;
  --color-accent: #7c5cfc;
  --color-accent-hover: #9478ff;
  --color-success: #34d399;
  --color-warning: #fbbf24;
  --color-error: #f87171;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

---

## Task 2: 路由和布局

### 路由表

| 路径                       | 页面                           | 布局      |
| -------------------------- | ------------------------------ | --------- |
| `/`                        | 重定向到 `/workspaces`         | —         |
| `/workspaces`              | WorkspaceListPage              | AppLayout |
| `/workspace/:id`           | WorkbenchPage（Chat + Canvas） | AppLayout |
| `/workspace/:id/documents` | DocumentsPage                  | AppLayout |
| `/settings`                | SettingsPage                   | AppLayout |

### 布局组件

```
AppLayout
├── GlobalNav (左侧窄栏: logo + workspace 切换 + 设置)
└── Content Area
    └── <Outlet />

WorkbenchPage
├── ChatPanel (左栏, 可折叠, 默认 40% 宽度)
│   ├── MessageList (对话流)
│   ├── CoTTree (思维链可折叠树)
│   ├── HITLCard (确认卡片)
│   └── InputArea (输入框 + 发送按钮)
└── CanvasPanel (右栏, 60% 宽度)
    ├── TabBar (editor / pdf / sandbox)
    └── TabContent
        ├── EditorTab (TipTap)
        ├── PDFTab (PDF 对照高亮)
        └── SandboxTab (代码执行结果)
```

---

## Task 3: 状态管理 + API 客户端

### Zustand Stores

```typescript
// useAgentStore.ts — SSE 实时状态
interface AgentState {
  messages: Message[];
  cotTree: CoTNode[];
  interrupt: InterruptData | null;
  isStreaming: boolean;
  currentNode: string | null;
  generatedContent: string;  // 流式 token 聚合

  // Actions
  addMessage: (msg: Message) => void;
  handleSSEEvent: (event: RunEvent) => void;
  clearInterrupt: () => void;
  reset: () => void;
}

// useLayoutStore.ts — UI 瞬态
interface LayoutState {
  sidebarCollapsed: boolean;
  splitRatio: number;         // Chat:Canvas 比例
  activeCanvasTab: 'editor' | 'pdf' | 'sandbox';
  toggleSidebar: () => void;
  setSplitRatio: (ratio: number) => void;
}
```

### API 客户端 + React Query Hooks

```typescript
// lib/api.ts
const api = axios.create({ baseURL: '/api' });
api.interceptors.request.use(config => {
  config.headers.Authorization = `Bearer ${getToken()}`;
  return config;
});

// hooks/useWorkspaces.ts
export function useWorkspaces() {
  return useQuery({ queryKey: ['workspaces'], queryFn: () => api.get('/workspaces') });
}

// hooks/useSSE.ts
export function useSSE(threadId: string, runId: string) {
  // EventSource 封装 + 自动重连 + Last-Event-ID
}
```

---

## Task 4: 核心页面

### ChatPanel 组件

| 子组件        | 功能                                                                               |
| ------------- | ---------------------------------------------------------------------------------- |
| `MessageList` | 渲染对话流（user/assistant 消息，支持 Markdown + 代码高亮）                        |
| `CoTTree`     | 可折叠的思维链树（从 `node_start/node_end` 事件构建）                              |
| `HITLCard`    | interrupt 事件触发的确认卡片（select_papers / confirm_execute / confirm_finalize） |
| `InputArea`   | 文本输入框 + Shift+Enter 换行 + Enter 发送                                         |

### HITLCard 三种类型

| action             | UI                                                  | 用户操作                                        |
| ------------------ | --------------------------------------------------- | ----------------------------------------------- |
| `select_papers`    | 论文列表（checkbox + abstract + relevance_comment） | 勾选 → resume `{"selected_ids": [...]}`         |
| `confirm_execute`  | 代码预览（语法高亮）                                | Approve/Reject → resume `{"action": "approve"}` |
| `confirm_finalize` | Markdown 预览                                       | Approve → resume / Reject → 推送 Canvas         |

### CanvasPanel 组件

| Tab        | 功能                                              |
| ---------- | ------------------------------------------------- |
| EditorTab  | TipTap 编辑器，Agent 生成内容自动填入，用户可手改 |
| PDFTab     | PDF 对照视图（MVP 可用 `react-pdf` 或 iframe）    |
| SandboxTab | 代码执行结果展示（stdout + 图表 iframe）          |

### 文档管理页

- 文件拖拽上传区（FileDropzone）
- 文档列表（标题 + 状态 badge + 操作按钮）
- 解析状态实时轮询更新

---

## Task 5: 拓展组件

### AcademicMarkdown 组件

```typescript
// 渲染学术 Markdown：
// - 标准 Markdown 语法
// - KaTeX 公式（$ inline $ 和 $$ block $$）
// - 代码块语法高亮
// - 文献引用角标（[1] 可点击跳转）
```

### StatusBar 组件

底部状态栏：当前执行节点名 + 耗时 + streaming 状态指示

---

## 验证清单

| 检查项     | 命令                     | 期望                  |
| ---------- | ------------------------ | --------------------- |
| 开发服务器 | `pnpm dev`               | localhost:5173 可访问 |
| 构建       | `pnpm build`             | 无错误                |
| TypeScript | `pnpm exec tsc --noEmit` | 0 errors              |
| Lint       | `pnpm exec eslint src/`  | 0 errors              |



