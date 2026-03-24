# 前端架构设计

> Research Copilot Web UI 的路由、状态管理、交互流程与组件工程化规范。

## 一、设计目标与约束

- **视觉基准**：Cursor 级 IDE 双栏布局 + 飞书/Notion 的温暖质感（圆角、柔和配色、舒适间距）
- **组件库**：shadcn/ui + Radix UI（headless，像素级可控）
- **状态哲学**：Event-Driven 分层响应式——REST 数据走 React Query，SSE 实时流走 Zustand，纯 UI 瞬态走 Zustand + localStorage
- **模块隔离**：Feature-Sliced 单向依赖，feature 之间禁止直接 import

---

## 二、技术决策记录

| 决策项           | 选择                             | 排除方案                  | 理由                                              |
| ---------------- | -------------------------------- | ------------------------- | ------------------------------------------------- |
| 设计范式         | Cursor 双栏 + 飞书视觉质感       | 纯 Chat UI / 纯编辑器     | 科研场景需要同时看对话和工作产物                  |
| 组件库           | shadcn/ui + Radix                | Ant Design / Arco Design  | 核心 UI 需深度定制，headless 不撞脸               |
| 状态管理         | React Query + Zustand 分层       | 单一 Zustand / Context    | 三类数据天然分离，Query 省大量 cache/loading 代码 |
| Chat↔Canvas 通信 | Zustand subscribe 响应式         | 事件总线 / props drilling | 无耦合、可 selector 优化渲染                      |
| URL 状态         | Path Params + Search Params 分层 | 全 Zustand / 全 URL       | 核心视图可分享可恢复，瞬态不污染 URL              |
| 文件上传         | S3 预签名直传                    | FastAPI 代理上传          | 大文件不经 BFF，带宽友好                          |
| PDF 渲染         | react-pdf (PDF.js)               | iframe 嵌入 / 自研渲染    | 支持自定义高亮覆盖层，生态成熟                    |
| 代码编辑器       | Monaco Editor                    | CodeMirror                | VS Code 同源，学术代码场景功能更全                |
| 富文本编辑器     | TipTap v2                        | BlockNote / Slate         | 扩展性最强，学术 Markdown + 公式支持好            |
| 样式方案         | Tailwind CSS 4 + CSS Variables   | CSS Modules / styled-comp | shadcn/ui 原生支持，主题切换方便                  |

---

## 三、页面与路由架构

### 3.1 路由树

```
/ → RootLayout (QueryClientProvider + ThemeProvider + Toaster)
├── /login              → LoginPage (第三方 Auth SDK 跳转)
├── /callback           → AuthCallback (OAuth 回调 → JWT 存储 → 跳转 /app)
└── /app                → AppLayout (AuthGuard + GlobalNav 顶部栏)
    ├── /app/workspaces  → WorkspaceListPage (课题空间网格/列表)
    └── /app/w/:workspaceId → WorkspaceLayout (Sidebar + <Outlet/>)
        ├── index            → WorkspaceDashboard (课题概览摘要)
        ├── /t/:threadId     → WorkbenchPage ★ (Chat + Canvas 双栏)
        ├── /documents       → DocumentListPage (文献管理)
        └── /settings        → SettingsPage (学科偏好 / BYOK / 用量)
```

### 3.2 Layout 嵌套层级

```
┌─────────────────────────────────────────────────────────────┐
│ RootLayout — QueryClientProvider + ThemeProvider + Toaster   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ AppLayout — AuthGuard + GlobalNav (顶部栏)              │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ WorkspaceLayout — Sidebar + <Outlet/>               │ │ │
│ │ │ ┌──────────┐ ┌──────────────────────────────────┐  │ │ │
│ │ │ │ Sidebar  │ │ WorkbenchPage                    │  │ │ │
│ │ │ │ Thread列表│ │ ┌────────┐ ┃ ┌────────────────┐ │  │ │ │
│ │ │ │ 文献库   │ │ │Chat    │ ┃ │Canvas (多Tab)  │ │  │ │ │
│ │ │ │ 设置     │ │ │Panel   │ ┃ │Editor/PDF/     │ │  │ │ │
│ │ │ │ +新建    │ │ │        │ ┃ │Sandbox         │ │  │ │ │
│ │ │ └──────────┘ │ └────────┘ ┃ └────────────────┘ │  │ │ │
│ │ │              └──────────────────────────────────┘  │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 URL 状态分层

| 状态类型     | 存储位置               | 示例                                  | 特征             |
| ------------ | ---------------------- | ------------------------------------- | ---------------- |
| **资源定位** | Path Params            | `/app/w/:workspaceId/t/:threadId`     | 决定数据加载     |
| **视图状态** | Search Params          | `?tab=pdf&docId=abc123`               | 可分享、刷新恢复 |
| **UI 瞬态**  | Zustand (部分 persist) | sidebarCollapsed, splitRatio, scrollY | 刷新丢失可接受   |

Search Params 枚举：

| 参数    | 说明                   | 取值                         |
| ------- | ---------------------- | ---------------------------- |
| `tab`   | Canvas 当前活跃 Tab    | `editor` / `pdf` / `sandbox` |
| `docId` | PDF Viewer 当前文档    | UUID                         |
| `runId` | Sandbox 当前查看的 Run | UUID                         |

### 3.4 关键设计决策

1. **三层 Layout 守卫**：RootLayout（Provider 注入）→ AppLayout（认证守卫，未登录跳 `/login`）→ WorkspaceLayout（Workspace 权限校验，无权限 403 页）
2. **侧边栏归 WorkspaceLayout**：进入 Workspace 后始终存在，可折叠。包含 Thread 历史列表、文献库入口、设置入口、新建对话按钮。类似飞书左侧导航
3. **可拖拽分栏**：WorkbenchPage 内 Chat 和 Canvas 用 `react-resizable-panels`，默认比例 2:3。比例持久化到 localStorage
4. **Canvas Tab 切换更新 URL**：切换 Tab 时 `setSearchParams({ tab: 'pdf', docId: '...' })`，支持浏览器前进/后退

---

## 四、状态管理与数据流

### 4.1 三层状态架构

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 1: React Query (TanStack Query v5)                            │
│ 职责：服务端数据缓存                                                │
│ 管理：Workspace CRUD · Document 列表/状态 · Thread 历史 · Run 历史  │
│       用户设置 · Workspace 摘要                                     │
│ 特性：自带 loading/error/cache/refetch/乐观更新/invalidateQueries   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2: Zustand — useAgentStore                                    │
│ 职责：SSE 实时流 → Agent 运行时状态                                 │
│ 字段：connectionStatus · currentRunId · executingNode               │
│       messages[] · interrupt · cotTree · generatedContent           │
│       executionResult · pdfHighlight                                │
│ 特性：Chat 和 Canvas 各自 subscribe 不同字段，精准重渲染            │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3: Zustand — useLayoutStore                                   │
│ 职责：纯前端 UI 瞬态                                                │
│ 字段：sidebarCollapsed · splitRatio · pdfScrollY · editorCursorPos  │
│       draftDirtyFlag                                                │
│ 特性：部分 persist → localStorage；页面切换自动清理瞬态字段         │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 useAgentStore 详细设计

```typescript
interface AgentState {
  // --- 连接状态 ---
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
  currentRunId: string | null
  lastEventSeq: number              // 断线重连用 Last-Event-ID

  // --- Chat 消费 ---
  messages: Message[]               // token 流逐字拼装的消息列表
  cotTree: CotNode[]                // 树形结构（支持并发节点）
  interrupt: InterruptPayload | null // HITL 挂起信息

  // --- Canvas 消费 ---
  generatedContent: string | null   // Agent 生成的编辑器内容
  executionResult: ExecutionResult | null // 沙盒执行结果 + 图表
  pdfHighlight: PdfHighlight | null // RAG 溯源高亮定位

  // --- Actions ---
  onRunEvent: (event: RunEvent) => void   // SSE 事件分发到对应字段
  resetForNewRun: () => void              // 新 Run 前清空
  hydrateFromActiveRun: (run: ActiveRunData) => void // 刷新恢复
}

// CoT 树节点（支持并发）
interface CotNode {
  nodeId: string
  parentNodeId: string | null       // null = 顶层节点
  nodeName: string                  // "discovery.search"
  status: 'pending' | 'running' | 'completed' | 'failed'
  startedAt: number | null
  completedAt: number | null
  children: CotNode[]               // 同级并列 = 并发执行
}
```

### 4.3 SSE 事件消费链路

```
FastAPI BFF ──SSE──► useAgentStream (Hook) ──► useAgentStore (Zustand) ──► 组件 subscribe
                     │                                                      │
                     ├ EventSource 生命周期管理                              ├ ChatPanel → messages, cotTree, interrupt
                     ├ RunEvent 解析 + 分发                                 ├ CanvasPanel (Editor) → generatedContent
                     ├ Last-Event-ID 断线重连                               ├ CanvasPanel (Sandbox) → executionResult
                     └ 连接状态上报                                          ├ CanvasPanel (PDF) → pdfHighlight
                                                                            └ StatusBar → executingNode, connectionStatus
```

### 4.4 useAgentStream Hook 职责

```typescript
function useAgentStream(threadId: string, runId: string | null): void {
  // 1. runId 存在时创建 EventSource 连接
  // 2. 解析 BFF 翻译后的 RunEvent，按 event_type 调用 useAgentStore 的 onRunEvent
  // 3. 维护 Last-Event-ID（= 最后收到的 seq），断线时自动重连并续传
  // 4. 组件卸载或 runId 变更时关闭旧连接
  // 5. run_end 事件触发后：
  //    - 关闭 EventSource
  //    - invalidateQueries(['threads', threadId]) → Thread 历史刷新
  //    - invalidateQueries(['documents']) → 文档状态刷新
}
```

### 4.5 React Query 使用规范

每个 feature 模块自含 `queries.ts`，导出 custom hooks：

```typescript
// features/workspace/queries.ts
export function useWorkspaces() {
  return useQuery({ queryKey: ['workspaces'], queryFn: api.getWorkspaces })
}
export function useWorkspaceSummary(id: string) {
  return useQuery({ queryKey: ['workspaces', id, 'summary'], queryFn: () => api.getWorkspaceSummary(id) })
}

// features/documents/queries.ts
export function useDocuments(workspaceId: string, filter?: ParseStatus) {
  return useQuery({
    queryKey: ['documents', workspaceId, filter],
    queryFn: () => api.getDocuments(workspaceId, filter),
    refetchInterval: (query) => dynamicPollingInterval(query.state.data),
  })
}
```

Query Key 约定：`['feature-name', ...resourceIds, ...filters]`。

### 4.6 组件通信范式

**Chat → Canvas**：Chat 接收 SSE → 写 `useAgentStore` → Canvas subscribe 对应字段自动更新。

**Canvas → Agent**：编辑器提交不经 store，走 API（`POST /runs` 携带 `editor_content` 字段）。

**跨 Feature 数据**：统一通过 `stores/` 或 React Query 共享缓存，禁止 feature 间直接 import。

---

## 五、核心交互流程

### 5.1 Chat ↔ Canvas 联动时序

```
① 用户在 ChatPanel 发送指令
   → POST /agent/threads/:id/runs → 返回 runId + stream URL

② useAgentStream 连接 SSE
   → EventSource 解析 RunEvent → 按 event_type 分发到 useAgentStore

③ ChatPanel 响应式渲染
   → subscribe(messages) → 流式拼字渲染
   → subscribe(cotTree)  → CoT 思维链树形面板
   → subscribe(executingNode) → 底部 StatusBar

④ CanvasPanel 被动联动
   → subscribe(generatedContent) → TipTap 编辑器自动更新
   → subscribe(executionResult) → Sandbox Tab 展示代码 + stdout + 图表
   → subscribe(pdfHighlight)    → PDF Tab 跳转到溯源段落
   → ⚡ Canvas 自动跳转到相关 Tab（如沙盒输出 → 自动切到 Sandbox Tab）

⑤ Run 结束 → invalidateQueries → Thread 历史 + 文档状态自动刷新
```

### 5.2 HITL 人类在环确认

SSE 收到 `interrupt` 事件后：

1. **ChatPanel**：渲染确认卡片（展示代码预览、操作说明 + 确认/拒绝按钮）
2. **CanvasPanel**：自动切到 Sandbox Tab，只读展示待执行代码
3. 用户点击「确认」→ `POST /runs/:id/resume` → 创建新 Run → 建立 parent_run_id 链 → 新 SSE 连接
4. 用户点击「拒绝」→ `POST /runs/:id/cancel` → Agent 优雅终止

#### 页面刷新与 HITL 状态水合

> 用户在 HITL 拦截等待时刷新页面，SSE 断开，Zustand 状态丢失。

**恢复策略**：进入 `/t/:threadId` 时，初始化请求 `GET /threads/:id/runs/active`：
- 返回 `status: 'requires_action'` → 调用 `useAgentStore.hydrateFromActiveRun(data)` → 重新渲染 HITL 确认卡片
- 返回 `status: 'running'` → 重新连接 SSE stream（带 `Last-Event-ID` 续传）
- 返回 `null` → 无活跃 Run，正常显示历史消息

### 5.3 Agent 执行状态可视化

两个组件协同展示 Agent 实时执行进度：

**StatusBar（底部状态栏）**：
- 始终显示：🟢 Running + 当前节点名（如 `discovery.search`）+ 已耗时
- subscribe → `executingNode`, `connectionStatus`
- 连接断开时显示 🔴 Disconnected + 重连倒计时

**CoTTree（思维链面板，Chat 区内折叠式）**：
- 节点级三态：✅ 已完成 / 🔄 执行中 / ⬚ 等待
- **支持并发渲染**：底层 `cotTree` 为树形结构（`CotNode[]` 含 `children`），同级并列节点可同时处于 🔄 状态
- 例如：`discovery` 节点下 `search_arxiv` 和 `search_pubmed` 并发执行时，树形控件展示为分叉

### 5.4 文件上传与解析状态

**上传流程**：
```
① 拖拽/选择文件 → POST /documents/upload-url → 获取预签名 URL + doc_id
② 前端直传 S3 → 显示上传进度条
③ POST /documents/confirm → 触发后台 Celery 解析
④ React Query refetchInterval 轮询 parse_status
```

**动态轮询退避策略**：

MinerU GPU 解析可能耗时数分钟至数十分钟。采用指数退避替代固定频率轮询：

```typescript
function dynamicPollingInterval(documents: Document[] | undefined): number | false {
  if (!documents) return false
  const hasPending = documents.some(d => ['pending', 'parsing'].includes(d.parseStatus))
  if (!hasPending) return false  // 无进行中任务，停止轮询

  // 根据最早进行中任务的开始时间计算退避间隔
  const oldestPending = findOldestPending(documents)
  const elapsedMs = Date.now() - oldestPending.createdAt
  if (elapsedMs < 30_000) return 3_000    // 前 30s: 每 3s
  if (elapsedMs < 120_000) return 10_000  // 30s-2min: 每 10s
  if (elapsedMs < 600_000) return 30_000  // 2-10min: 每 30s
  return 60_000                            // >10min: 每 60s
}
```

**侧边栏文献状态指示**：三种视觉状态 ✅ 解析完成（可点击打开）/ 🔄 解析中（进度条/转圈）/ ❌ 解析失败（重试链接）

---

## 六、组件架构与工程化

### 6.1 目录结构

```
frontend/src/
├── app/                          # 应用入口 + 路由 + Provider
│   ├── App.tsx                   # 根组件
│   ├── router.tsx                # React Router 路由配置
│   ├── providers.tsx             # QueryClient + Theme + Toast 组合
│   ├── RootLayout.tsx            # 全局 Provider 注入层
│   └── AppLayout.tsx             # 认证守卫 + GlobalNav
│
├── components/
│   ├── ui/                       # shadcn/ui 基础组件 (Button, Dialog, Tabs, DropdownMenu...)
│   └── shared/                   # 跨 feature 复用组件
│       ├── AcademicMarkdown.tsx   # Markdown + KaTeX 数学公式渲染
│       ├── StatusBar.tsx          # 底部 Agent 状态栏
│       ├── DragSplit.tsx          # 可拖拽分栏容器
│       └── FileDropzone.tsx       # 文件拖拽上传区
│
├── features/                      # 核心业务模块
│   ├── auth/                      # 认证流程
│   │   ├── LoginPage.tsx
│   │   ├── AuthCallback.tsx
│   │   └── useAuth.ts
│   │
│   ├── workspace/                 # 课题空间管理
│   │   ├── WorkspaceListPage.tsx
│   │   ├── WorkspaceLayout.tsx    # Sidebar + <Outlet/>
│   │   ├── WorkspaceDashboard.tsx
│   │   ├── Sidebar.tsx
│   │   ├── queries.ts
│   │   └── types.ts
│   │
│   ├── chat/                      # 左栏对话区
│   │   ├── ChatPanel.tsx
│   │   ├── ChatInput.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── HITLCard.tsx           # HITL 确认卡片
│   │   ├── CoTTree.tsx            # 思维链树形面板
│   │   ├── useAgentStream.ts      # SSE 连接管理 Hook
│   │   ├── queries.ts
│   │   └── types.ts
│   │
│   ├── canvas/                    # 右栏多 Tab 工作区
│   │   ├── CanvasPanel.tsx        # Tab 容器
│   │   ├── CanvasTabBar.tsx       # Tab 切换栏
│   │   ├── editor/                # TipTap 富文本
│   │   │   ├── TiptapEditor.tsx
│   │   │   └── useEditorDraft.ts  # 防抖自动保存草稿
│   │   ├── pdf/                   # PDF 阅读器
│   │   │   ├── PdfViewer.tsx
│   │   │   ├── PdfHighlight.tsx   # RAG 溯源高亮覆盖层
│   │   │   └── usePdfNavigation.ts
│   │   ├── sandbox/               # 沙盒 IDE
│   │   │   ├── SandboxIDE.tsx     # Monaco 编辑器
│   │   │   ├── CodePreview.tsx    # HITL 只读代码预览
│   │   │   └── ChartRenderer.tsx  # Matplotlib/图表展示
│   │   ├── queries.ts
│   │   └── types.ts
│   │
│   ├── documents/                 # 文献管理
│   │   ├── DocumentListPage.tsx
│   │   ├── DocumentUploader.tsx
│   │   ├── useUploadFlow.ts       # 上传流程 Hook
│   │   ├── queries.ts
│   │   └── types.ts
│   │
│   ├── settings/                  # 设置
│   │   ├── SettingsPage.tsx
│   │   ├── DisciplineSelector.tsx
│   │   ├── BYOKForm.tsx
│   │   ├── UsageStats.tsx
│   │   ├── queries.ts
│   │   └── types.ts
│   │
│   └── workbench/                 # WorkbenchPage 组装层
│       └── WorkbenchPage.tsx      # 组装 ChatPanel + CanvasPanel
│
├── stores/                        # Zustand 全局 stores
│   ├── useAgentStore.ts           # SSE 实时状态
│   └── useLayoutStore.ts          # UI 瞬态
│
├── lib/                           # 工具函数
│   ├── api-client.ts              # Axios 实例 + 拦截器
│   ├── cn.ts                      # clsx + twMerge
│   ├── url-state.ts               # Search Params 读写封装
│   └── polling.ts                 # 动态退避轮询函数
│
└── types/                         # 全局 TS 类型（对齐后端 schemas）
    ├── agent.ts                   # RunEvent, Message, InterruptPayload, CotNode
    ├── document.ts                # DocumentMeta, ParseStatus
    ├── workspace.ts               # Workspace, Thread, WorkspaceSummary
    └── common.ts                  # UUID, Pagination, ApiError
```

### 6.2 Feature 模块内部规范

| 文件         | 职责                             | 规则                                          |
| ------------ | -------------------------------- | --------------------------------------------- |
| `queries.ts` | React Query hooks（useXxx 风格） | Query key 约定：`['feature', ...params]`      |
| `types.ts`   | Feature 私有类型                 | 全局共享类型放 `src/types/`，内部专用放模块内 |
| `index.ts`   | Barrel export                    | Feature 对外唯一出口，只导出公开 API          |

**禁止规则**：
- ❌ 跨 feature 直接 import 内部文件（如 `import { CoTTree } from '../chat/CoTTree'`）
- ✅ 只 import feature 的 barrel export（如 `import { ChatPanel } from '@/features/chat'`）
- 需要跨 feature 共享的组件？提升到 `components/shared/`

### 6.3 模块依赖关系

```
Pages (workbench/WorkbenchPage)
  ↓ 组装
Features (chat/ · canvas/ · workspace/ · documents/ · settings/)
  ↓ 使用             ← ❌ features 之间禁止直接 import
Shared (components/ui · components/shared · stores/)
  ↓ 使用
Foundation (lib/ · types/)
```

chat/ 和 canvas/ 的核心通信路径：`chat/ → stores/useAgentStore ← canvas/`

### 6.4 工具链

| 类别     | 选型                                                    | 版本   |
| -------- | ------------------------------------------------------- | ------ |
| 构建     | Vite                                                    | 6.x    |
| 语言     | TypeScript (strict mode)                                | 5.5+   |
| 框架     | React + React Router                                    | 19 + 7 |
| 样式     | Tailwind CSS + CSS Variables + class-variance-authority | 4.x    |
| 数据     | TanStack Query                                          | v5     |
| 状态     | Zustand                                                 | v5     |
| 校验     | zod                                                     | 3.x    |
| 富文本   | TipTap                                                  | v2     |
| 代码编辑 | Monaco Editor (via @monaco-editor/react)                | —      |
| 数学公式 | KaTeX                                                   | —      |
| PDF      | react-pdf (基于 PDF.js) + 虚拟滚动                      | —      |
| HTTP     | Axios                                                   | —      |
| 代码质量 | ESLint + Prettier                                       | —      |
| 单元测试 | Vitest + React Testing Library                          | —      |
| E2E 测试 | Playwright                                              | —      |

---

## 七、与其他 Spec 的对齐

### 7.1 与 FastAPI BFF Spec 的接口对齐

| 前端模块             | 依赖的 BFF API                                               | 补充需求                   |
| -------------------- | ------------------------------------------------------------ | -------------------------- |
| chat/ useAgentStream | `GET /agent/threads/:id/runs/:run_id/stream`                 | —                          |
| chat/ HITLCard       | `POST /agent/threads/:id/runs/:run_id/resume`                | —                          |
| chat/ (刷新恢复)     | **新增** `GET /agent/threads/:id/runs/active`                | 返回当前活跃/挂起 Run 信息 |
| documents/           | `POST /documents/upload-url` · `/confirm` · `GET /documents` | —                          |
| canvas/ editor       | `PUT /editor/draft` · `GET /editor/draft/:thread_id`         | —                          |

### 7.2 与 ARCHITECT.md 的变更

本 Spec 细化并部分调整了 ARCHITECT.md 中的前端目录结构：
- `features/` 下新增 `workbench/` 模块作为 Page 组装层
- `store/` 重命名为 `stores/`（复数，与 features 对齐）
- 新增 `app/` 目录承载路由和 Layout
- `components/` 增加 `shared/` 子目录区分 shadcn/ui 和自定义组件
