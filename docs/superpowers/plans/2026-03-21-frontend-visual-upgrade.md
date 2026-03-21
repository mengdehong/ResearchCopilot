# Frontend Visual Upgrade Implementation Plan

**Goal:** 将 Research Copilot 前端从 vanilla CSS 迁移至 Tailwind CSS + shadcn/ui + Framer Motion，实现双主题（暗色/浅色）、丰富微动效、全站视觉升级。
**Architecture:** 分层迁移 — Phase 1 搭建基础设施（Tailwind/shadcn/theme/motion），Phase 2 重构全局布局，Phase 3 逐页面重写组件，Phase 4 后端适配用户偏好 API，Phase 5 清理旧 CSS + 全流程验证。
**Tech Stack:** Tailwind CSS 4, shadcn/ui, Framer Motion, react-resizable-panels, @tanstack/react-virtual
**Design Spec:** `docs/superpowers/specs/2026-03-21-frontend-visual-upgrade-design.md`

---

## Phase 1: 基础设施 (依赖安装 + 设计系统 + 主题 + 动画)

### Task 1: 安装 Tailwind + shadcn/ui + 新增依赖

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Create: `frontend/components.json`

- [ ] **Step 1:** 安装核心依赖
  ```bash
  cd frontend && npm install tailwindcss @tailwindcss/vite framer-motion react-resizable-panels @tanstack/react-virtual
  ```
- [ ] **Step 2:** 配置 `vite.config.ts` — 添加 `@tailwindcss/vite` 插件
- [ ] **Step 3:** 初始化 shadcn/ui
  ```bash
  cd frontend && npx shadcn@latest init
  ```
- [ ] **Step 4:** 安装所需 shadcn 组件
  ```bash
  npx shadcn@latest add button dialog tabs input label select popover avatar badge tooltip
  ```
- [ ] **Step 5:** 验证编译
  ```bash
  cd frontend && npm run build
  ```

### Task 2: 设计系统 — 重写 index.css 为双主题 CSS 变量

**Files:**
- Rewrite: `frontend/src/index.css`

- [ ] **Step 1:** 替换 `index.css` 全部内容为：
  - Tailwind directives (`@import "tailwindcss"`)
  - `:root` 浅色模式 CSS 变量（来自设计文档 §2.1）
  - `.dark` 深色模式 CSS 变量
  - 全局 reset + 基础样式
  - shadcn/ui 需要的 `@layer base` 配置
- [ ] **Step 2:** 验证 `npm run build` 编译通过

### Task 3: ThemeProvider + useTheme hook

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`
- Modify: `frontend/src/app/RootLayout.tsx`

- [ ] **Step 1:** 创建 `useTheme.ts`
  ```typescript
  // 逻辑：
  // 1. 读取 localStorage('theme') → 'light' | 'dark' | 'system'
  // 2. system 时跟随 prefers-color-scheme
  // 3. 设置 document.documentElement.classList.add/remove('dark')
  // 4. 导出 { theme, setTheme, resolvedTheme }
  ```
- [ ] **Step 2:** 在 `RootLayout.tsx` 中调用 `useTheme()` 初始化
- [ ] **Step 3:** 验证：手动切换 class 后 CSS 变量正确切换

### Task 4: 通用动画组件

**Files:**
- Create: `frontend/src/components/shared/MotionWrappers.tsx`

- [ ] **Step 1:** 创建复用动画 wrapper 组件：
  - `FadeIn` — opacity 0→1
  - `SlideUp` — y: 8→0 + opacity
  - `StaggerContainer` + `StaggerItem` — 列表交错入场
  - `ScaleIn` — scale 0.95→1 + opacity（用于 Dialog）
- [ ] **Step 2:** 内置 `prefers-reduced-motion` 降级 + 列表 > 50 项禁用 stagger
- [ ] **Step 3:** 验证：在临时页面测试动画效果

---

## Phase 2: 布局重构

### Task 5: AppLayout — 可折叠双栏侧边栏

**Files:**
- Rewrite: `frontend/src/app/AppLayout.tsx`
- Delete: `frontend/src/app/AppLayout.css`
- Modify: `frontend/src/stores/useLayoutStore.ts` — 增加 `navExpanded` 状态

**Steps:**
- [ ] **Step 1:** 在 `useLayoutStore` 中添加 `navExpanded: boolean` + `toggleNav()`
- [ ] **Step 2:** 重写 `AppLayout.tsx`:
  - 收起态 (56px)：Logo "R" + 图标按钮（工作区、设置）
  - 展开态 (240px)：Logo + 产品名 + 工作区选择器（Select）+ Thread 历史列表 + 底部主题切换 + 用户头像
  - 使用 Framer Motion `animate={{ width }}` spring 动画展开/收起
  - Thread 历史列表接入 `useThreads()` + `@tanstack/react-virtual`
- [ ] **Step 3:** 删除 `AppLayout.css`
- [ ] **Step 4:** 验证：侧边栏展开收起动画流畅，Thread 列表正确加载
- [ ] **Step 5:** Commit `refactor(ui): redesign AppLayout with collapsible sidebar`

### Task 6: WorkbenchPage — react-resizable-panels 双栏

**Files:**
- Rewrite: `frontend/src/features/workbench/WorkbenchPage.tsx`
- Delete: `frontend/src/features/workbench/WorkbenchPage.css`
- Delete: `frontend/src/components/shared/StatusBar.tsx`（Agent 状态移入 ChatPanel 头部）
- Delete: `frontend/src/components/shared/StatusBar.css`

**Steps:**
- [ ] **Step 1:** 替换手动 flex 分割为 `PanelGroup` + `Panel` + `PanelResizeHandle`
- [ ] **Step 2:** 设置 minSize，PanelResizeHandle 带 hover 高亮
- [ ] **Step 3:** 拖拽遮罩: `onDragging` 回调中给两侧注入 `pointer-events: none`
- [ ] **Step 4:** 删除旧 CSS + StatusBar 组件
- [ ] **Step 5:** 验证：拖拽 60fps 流畅，双击恢复默认
- [ ] **Step 6:** Commit `refactor(ui): replace manual split with react-resizable-panels`

---

## Phase 3: 页面重设计

### Task 7: WorkspaceListPage 重写

**Files:**
- Rewrite: `frontend/src/features/workspace/WorkspaceListPage.tsx`
- Delete: `frontend/src/features/workspace/WorkspaceListPage.css`

**Steps:**
- [ ] **Step 1:** 重写为水平卡片网格 + 学科渐变色块 + shadcn Badge
- [ ] **Step 2:** 新建工作区改为 "+" 虚线卡片 → shadcn Dialog
- [ ] **Step 3:** 空状态引导 UI
- [ ] **Step 4:** 卡片 `StaggerContainer` + `StaggerItem` fade-up 入场
- [ ] **Step 5:** 删除旧 CSS，验证创建/删除/跳转全流程
- [ ] **Step 6:** Commit `refactor(ui): redesign WorkspaceListPage with shadcn components`

### Task 8: ChatPanel + 消息组件重写

**Files:**
- Rewrite: `frontend/src/features/chat/ChatPanel.tsx`
- Rewrite: `frontend/src/features/chat/MessageList.tsx`
- Rewrite: `frontend/src/features/chat/InputArea.tsx`
- Rewrite: `frontend/src/features/chat/CoTTree.tsx`
- Rewrite: `frontend/src/features/chat/HITLCard.tsx`
- Delete: `frontend/src/features/chat/ChatPanel.css`
- Delete: `frontend/src/features/chat/MessageList.css`
- Delete: `frontend/src/features/chat/InputArea.css`
- Delete: `frontend/src/features/chat/CoTTree.css`
- Delete: `frontend/src/features/chat/HITLCard.css`

**Steps:**
- [ ] **Step 1:** ChatPanel 头部：工作区名称 + Agent 状态指示灯 (idle/thinking/executing)
- [ ] **Step 2:** MessageList：全部左对齐通栏，avatar + 背景色 + 左侧 2px accent 竖线
- [ ] **Step 3:** SSE 流式安全：`isStreaming` 时仅 CSS `@keyframes blink` 光标，`useRef` 管理流式文本
- [ ] **Step 4:** CoTTree：thinking 自动展开 + auto-scroll，完成自动折叠（`AnimatePresence`，仅非 streaming 触发）
- [ ] **Step 5:** HITLCard：Approve = accent 实色 Button，Reject = ghost Button + shadcn Popover 二次确认
- [ ] **Step 6:** InputArea：大圆角 Input + 发送按钮 loading spinner
- [ ] **Step 7:** 消息入场 `SlideUp` 动效
- [ ] **Step 8:** 删除所有 5 个旧 CSS
- [ ] **Step 9:** 验证：发消息 → SSE 流式 → CoT 展开/折叠 → HITL 交互
- [ ] **Step 10:** Commit `refactor(ui): redesign ChatPanel with full-width messages and motion`

### Task 9: CanvasPanel 重写

**Files:**
- Rewrite: `frontend/src/features/canvas/CanvasPanel.tsx`
- Rewrite: `frontend/src/features/canvas/EditorTab.tsx`
- Delete: `frontend/src/features/canvas/CanvasPanel.css`
- Delete: `frontend/src/features/canvas/EditorTab.css`
- Delete: `frontend/src/features/canvas/PDFTab.css`
- Delete: `frontend/src/features/canvas/SandboxTab.css`

**Steps:**
- [ ] **Step 1:** Tab 栏：shadcn Tabs + Framer Motion `layoutId` 下划线滑动
- [ ] **Step 2:** Tab 溢出：`overflow-x-auto scrollbar-hide` + overflow dropdown
- [ ] **Step 3:** 工具栏图标分组 + shadcn Tooltip
- [ ] **Step 4:** 编辑器加大 padding + line-height
- [ ] **Step 5:** 删除 4 个旧 CSS
- [ ] **Step 6:** 验证：Tab 切换 + 编辑器保存 + PDF Tab
- [ ] **Step 7:** Commit `refactor(ui): redesign CanvasPanel with shadcn Tabs`

### Task 10: SettingsPage + Auth 页面重写

**Files:**
- Rewrite: `frontend/src/features/settings/SettingsPage.tsx`
- Delete: `frontend/src/features/settings/SettingsPage.css`
- Rewrite: `frontend/src/features/auth/components/AuthLayout.tsx`
- Rewrite: `frontend/src/features/auth/pages/LoginPage.tsx`
- Rewrite: `frontend/src/features/auth/pages/RegisterPage.tsx`
- Delete: `frontend/src/features/auth/auth.css`

**Steps:**
- [ ] **Step 1:** SettingsPage：分组 surface 卡片，shadcn Input/Label/Select，主题切换卡片调用 `useTheme`
- [ ] **Step 2:** AuthLayout：居中 surface 卡片 + shadow-lg + `ScaleIn` 入场
- [ ] **Step 3:** LoginPage/RegisterPage：shadcn Input + Label + Button(loading)
- [ ] **Step 4:** 删除 2 个旧 CSS
- [ ] **Step 5:** 验证：设置保存 + 主题切换 + 登录注册流程
- [ ] **Step 6:** Commit `refactor(ui): redesign SettingsPage and Auth pages`

---

## Phase 4: 后端适配

### Task 11: 用户主题偏好 API

**Files:**
- Modify: `backend/api/routers/auth.py` — 添加 `PATCH /api/auth/me/settings`
- Modify: `backend/api/schemas/auth.py` — 添加 `UserSettingsUpdate`
- Create: `tests/unit/test_api_user_settings.py`

**Steps:**
- [ ] **Step 1:** 添加 `UserSettingsUpdate` schema
  ```python
  class UserSettingsUpdate(BaseModel):
      theme: Literal["light", "dark", "system"] = "system"
  ```
- [ ] **Step 2:** 添加端点
  ```python
  @router.patch("/me/settings")
  async def update_user_settings(
      body: UserSettingsUpdate,
      session: AsyncSession = Depends(get_db),
      current_user: User = Depends(get_current_user),
  ) -> dict:
      current_user.settings = {**current_user.settings, **body.model_dump(exclude_unset=True)}
      session.add(current_user)
      await session.commit()
      return current_user.settings
  ```
- [ ] **Step 3:** 前端 `useTheme` 切换时调用 `api.patch('/auth/me/settings', { theme })`
- [ ] **Step 4:** 编写单测
  ```bash
  python -m pytest tests/unit/test_api_user_settings.py -v
  ```
- [ ] **Step 5:** Commit `feat(api): add user theme preference endpoint`

---

## Phase 5: 清理与验证

### Task 12: 清理旧 CSS + 最终验证

**Files to delete (17 files):**
- `frontend/src/app/AppLayout.css`
- `frontend/src/components/shared/AcademicMarkdown.css`
- `frontend/src/components/shared/StatusBar.css`
- `frontend/src/features/auth/auth.css`
- `frontend/src/features/canvas/CanvasPanel.css`
- `frontend/src/features/canvas/EditorTab.css`
- `frontend/src/features/canvas/PDFTab.css`
- `frontend/src/features/canvas/SandboxTab.css`
- `frontend/src/features/chat/ChatPanel.css`
- `frontend/src/features/chat/CoTTree.css`
- `frontend/src/features/chat/HITLCard.css`
- `frontend/src/features/chat/InputArea.css`
- `frontend/src/features/chat/MessageList.css`
- `frontend/src/features/documents/DocumentsPage.css`
- `frontend/src/features/settings/SettingsPage.css`
- `frontend/src/features/workbench/WorkbenchPage.css`
- `frontend/src/features/workspace/WorkspaceListPage.css`

**Steps:**
- [ ] **Step 1:** 删除所有 17 个旧 CSS，移除对应 TSX 中的 import
- [ ] **Step 2:** 验证编译
  ```bash
  cd frontend && npm run build
  ```
- [ ] **Step 3:** 验证 lint
  ```bash
  cd frontend && npm run lint
  ```
- [ ] **Step 4:** 浏览器全流程验证
- [ ] **Step 5:** Commit `chore(ui): remove legacy CSS files`
