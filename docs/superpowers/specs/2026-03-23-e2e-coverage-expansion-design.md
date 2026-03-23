# 前端 Playwright E2E 测试覆盖扩展设计

> **目标**：将前端 E2E 测试从现有 5 个 spec（43 个用例，覆盖 WorkbenchPage + DocumentsPage）扩展到全页面覆盖。
> **日期**：2026-03-23
> **状态**：✅ 已完成（82 用例 / 13 个 spec）

---

## 一、当前状态

| 已覆盖页面 | Spec 文件 | 用例数 |
|-----------|----------|--------|
| WorkbenchPage (Chat Flow) | `chat-flow.spec.ts` | 8 |
| WorkbenchPage (Thread Switch) | `thread-switch.spec.ts` | 6 |
| WorkbenchPage (HITL) | `hitl-interrupt.spec.ts` | 8 |
| WorkbenchPage (Editor) | `editor-canvas.spec.ts` | 7 |
| DocumentsPage | `documents.spec.ts` | 8 |
| **合计** | **5 个 spec** | **43** |

### 未覆盖页面

| 页面 | 路由 | Guard |
|------|------|-------|
| LoginPage | `/login` | GuestGuard |
| RegisterPage | `/register` | GuestGuard |
| ForgotPasswordPage | `/forgot-password` | GuestGuard |
| ResetPasswordPage | `/reset-password` | GuestGuard |
| VerifyEmailPage | `/verify-email` | GuestGuard |
| OAuthCallbackPage | `/oauth/callback` | 无 Guard |
| WorkspaceListPage | `/workspaces` | AuthGuard |
| SettingsPage | `/settings` | AuthGuard |

---

## 二、测试策略

### 2.1 双 Fixture 体系

现有 `authedPage` fixture（注入 token + mock API）仅适用于 AuthGuard 保护的页面。Auth 页面在 GuestGuard 下，需要**未认证**的 page：

```
fixtures.ts 新增:
  guestPage  — 不注入 token，只设置 locale=en，不调用 setupDefaultMocks
  authedPage — (已有) 注入 token + 全 API mock
```

### 2.2 Auth 页面两层测试

| 层级 | Spec 文件 | 后端依赖 | 覆盖内容 |
|------|----------|---------|---------|
| Mock UI | `auth-login.spec.ts`, `auth-register.spec.ts`, `auth-flows.spec.ts` | `page.route()` mock | 表单交互、校验、错误显示、导航链接 |
| Smoke | `auth-smoke.spec.ts` | 真实后端 | 注册 → 登录 → 跳转全链路 |

smoke 测试通过 Playwright `projects` 配置单独控制：

```ts
// playwright.config.ts 新增 project
{
    name: 'smoke',
    testMatch: '**/*-smoke.spec.ts',
    use: { ...devices['Desktop Chrome'] },
}
```

### 2.3 API Mock 策略

Auth 页面的 mock 直接在各 spec 文件中通过 `page.route()` 注入，不污染现有 `setupDefaultMocks`。

---

## 三、新增文件与用例

### 3.1 `auth-login.spec.ts` — 登录页 Mock UI 测试

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 页面渲染 | 导航到 `/login` | 标题 "Welcome back"、email/password 输入框、提交按钮可见 |
| 2 | 成功登录 → 跳转 | mock `POST /auth/login` → 200，填写表单提交 | 跳转到 `/workspaces` |
| 3 | 错误凭据 → 错误提示 | mock `POST /auth/login` → 401 detail | 显示错误文本 |
| 4 | 表单校验 — 空提交 | 不填写直接点提交 | 浏览器原生校验阻止提交 |
| 5 | "Forgot password?" 链接 | 点击链接 | 导航到 `/forgot-password` |
| 6 | "Sign up" 链接 | 点击链接 | 导航到 `/register` |
| 7 | OAuth 按钮存在 | 渲染页面 | OAuth 按钮可见 |

### 3.2 `auth-register.spec.ts` — 注册页 Mock UI 测试

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 页面渲染 | 导航到 `/register` | 标题 "Start your research journey"、3 个输入框可见 |
| 2 | 成功注册 → 验证提示 | mock `POST /auth/register` → 200 | 显示 "Verify your email" 成功界面 |
| 3 | 重复邮箱 → 错误提示 | mock → 409 | 显示错误文本 |
| 4 | "Sign in" 链接 | 点击链接 | 导航到 `/login` |
| 5 | 成功后 "Back to login" | 注册成功后点链接 | 导航到 `/login` |

### 3.3 `auth-flows.spec.ts` — 密码重置 & 邮箱验证

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | ForgotPassword 渲染 | 导航到 `/forgot-password` | 标题 "Reset your password"、email 输入、提交按钮 |
| 2 | 发送成功 → 提示 | mock `POST /auth/forgot-password` → 200 | 显示 "a reset link has been sent" |
| 3 | 发送失败 → 错误 | mock → 500 | 显示错误文本 |
| 4 | ResetPassword 有 token → 表单 | 导航到 `/reset-password?token=abc` | 密码输入框 + 提交按钮可见 |
| 5 | ResetPassword 无 token → 错误 | 导航到 `/reset-password` | 显示错误 "Failed to reset password" |
| 6 | 重置成功 | mock `POST /auth/reset-password` → 200 | 显示 "Password reset successfully!" |
| 7 | VerifyEmail 有 token → 成功 | mock `POST /auth/verify-email` → 200 | 显示 "Email verified successfully!" |
| 8 | VerifyEmail 有 token → 失败 | mock → 400 | 显示 "Verification failed" |
| 9 | VerifyEmail 无 token | 导航到 `/verify-email` | 显示错误状态 |

### 3.4 `auth-smoke.spec.ts` — 需真实后端的全链路

> 需要 `npm run dev` + 后端 `make dev` 同时运行

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 注册 → 登录全链路 | 注册新用户（跳过邮箱验证）→ 登录 | 成功跳转到 `/workspaces` |
| 2 | 错误密码被拒 | 用错误密码登录 | 显示错误提示 |

### 3.5 `workspace-list.spec.ts` — Workspace 列表页

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 列表渲染 | 导航到 `/workspaces` | "Workspace 1" 卡片 + discipline badge 可见 |
| 2 | 空列表 → empty state | mock 返回 `[]` | "No workspaces yet" + 创建按钮可见 |
| 3 | 创建 workspace → dialog | 点击 "New Workspace" | Dialog 出现：name input + discipline select |
| 4 | 创建成功 → 列表刷新 | 填写名称 → 点创建 → mock `POST /workspaces` → 200 | Dialog 关闭 |
| 5 | 点击卡片 → 导航 | 点击 workspace 卡片 | URL 变为 `/workspace/ws-1` |
| 6 | 删除 workspace | hover 卡片 → 点击 trash 图标 | mock `DELETE /workspaces/ws-1` 被调用 |
| 7 | loading 骨架屏 | 延迟 API 响应 | 骨架屏可见 |

### 3.6 `settings.spec.ts` — 设置页

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 页面渲染 | 导航到 `/settings` | 标题 "Settings"、所有 card 可见 |
| 2 | 账户信息显示 | 渲染 | 显示 "Test User"、"test@example.com" |
| 3 | 主题切换 — Dark | 点击 "Dark" 按钮 | 按钮高亮 + `<html>` 添加 `.dark` class |
| 4 | 语言切换 — 中文 | 选择 "中文" | 页面文本切换为中文 |
| 5 | API Key 保存 | 输入 key → 点 Save | 显示 "✓ Saved" |
| 6 | Quota 用量显示 | 渲染 | 显示 "1.0K / 10.0K" + 进度条 |
| 7 | Sign Out 按钮 | 点击 Sign Out | 导航到 `/login` |

### 3.7 `pdf-viewer.spec.ts` — PDF 查看器

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 空状态 | 切换到 PDF tab，无 activePdf | 显示 "PDF Viewer" 占位文案 |
| 2 | SSE 自动切换 | 发送消息 → mock `pdf_highlight` SSE 事件 | tab 自动切换到 PDF，显示 `Doc: doc-xxx` |
| 3 | 文本摘要 | `pdf_highlight` 携带 `text_snippet` | 工具栏显示摘要文本 |
| 4 | 加载态 | 延迟 `/documents/:id/download` 响应 | 显示 "Loading PDF..." |
| 5 | 下载失败 | mock download → 500 | 显示 "Failed to load PDF" |
| 6 | iframe 页码锚点 | `pdf_highlight` page=5 | iframe src 包含 `#page=5` |

### 3.8 `sse-reconnect.spec.ts` — SSE 重连

| # | 用例名 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 错误后重连 | mock 首次连接 error → 重连成功 | 重连后事件正常送达 |
| 2 | run_end 停止 streaming | SSE 发送 `run_end` 事件 | Stop 按钮消失 |
| 3 | 线程切换加载历史 | URL 从 `?thread=th-1` 变为 `?thread=th-2` | 新线程消息显示，旧消息消失 |
| 4 | 流式指示器 | SSE 连接活跃中 | Stop 按钮可见，节点名称显示 |

---

## 四、基础设施变更

### 4.1 `fixtures.ts` 扩展

新增 `guestPage` fixture：

```ts
export const test = base.extend<{ authedPage: Page; guestPage: Page }>({
    // authedPage — 已有，不变

    guestPage: async ({ page }, use) => {
        await page.addInitScript(() => {
            localStorage.setItem('locale', 'en')
        })
        // 不注入 token，不设置 API mock
        // Mock auth/refresh 返回 401 使 GuestGuard 放行
        await page.route('**/api/v1/auth/refresh', (route) =>
            route.fulfill({ status: 401, json: { detail: 'No token' } }),
        )
        await use(page)
    },
})
```

### 4.2 `playwright.config.ts` 扩展

新增 `smoke` project：

```ts
projects: [
    {
        name: 'chromium',
        use: { ...devices['Desktop Chrome'] },
        testIgnore: '**/*-smoke.spec.ts',
    },
    {
        name: 'smoke',
        testMatch: '**/*-smoke.spec.ts',
        use: { ...devices['Desktop Chrome'] },
    },
],
```

### 4.3 `helpers/api-mocks.ts`

新增 `setupAuthMocks(page)` — 用于 auth spec 文件中 mock auth API：

```ts
export async function setupAuthMocks(page: Page): Promise<void> {
    await page.route('**/api/v1/auth/login', (route) => {
        // 默认成功，各测试可覆盖
        return route.fulfill({
            json: { access_token: 'new-token', user: MOCK_USER },
        })
    })
    await page.route('**/api/v1/auth/register', (route) =>
        route.fulfill({ status: 200, json: { message: 'ok' } }),
    )
    // ... forgot-password, reset-password, verify-email
}
```

---

## 五、文件组织

```
e2e/
├── auth-login.spec.ts          ← [NEW] 7 用例
├── auth-register.spec.ts       ← [NEW] 5 用例
├── auth-flows.spec.ts          ← [NEW] 9 用例
├── auth-smoke.spec.ts          ← [NEW] 2 用例（需真实后端）
├── workspace-list.spec.ts      ← [NEW] 7 用例
├── settings.spec.ts            ← [NEW] 7 用例
├── pdf-viewer.spec.ts          ← [NEW] 6 用例
├── sse-reconnect.spec.ts       ← [NEW] 4 用例
├── chat-flow.spec.ts           ← (已有，8 用例)
├── documents.spec.ts           ← (已有，重命名，8 用例)
├── editor-canvas.spec.ts       ← (已有，重命名，7 用例)
├── hitl-interrupt.spec.ts      ← (已有，8 用例)
├── thread-switch.spec.ts       ← (已有，6 用例)
├── fixtures.ts                 ← [MODIFY] 新增 guestPage
└── helpers/
    ├── api-mocks.ts            ← [MODIFY] 新增 setupAuthMocks
    └── sse-mocks.ts            ← [MODIFY] 重写 onmessage 轮询 + MAX_POLLS
```

**实际新增**：47 个用例（设计 37 + 追加 10），总计 82 个用例

---

## 六、实施顺序

| 阶段 | 任务 | 先决条件 |
|------|------|---------|
| 1 | 扩展 `fixtures.ts` + `api-mocks.ts` | 无 |
| 2 | `workspace-list.spec.ts` | 阶段 1 |
| 3 | `settings.spec.ts` | 阶段 1 |
| 4 | `auth-login.spec.ts` | 阶段 1 |
| 5 | `auth-register.spec.ts` | 阶段 1 |
| 6 | `auth-flows.spec.ts` | 阶段 1 |
| 7 | `auth-smoke.spec.ts` + `playwright.config.ts` | 阶段 1 |
| 8 | 验证全部通过 | 阶段 1-7 |

---

## 七、验证计划

### 自动化验证

```bash
# 跑所有 mock 测试（不含 smoke）
cd frontend && npx playwright test --project=chromium

# 跑 smoke 测试（需后端运行）
cd frontend && npx playwright test --project=smoke
```

### 验证标准

- 所有新测试用例通过（`npx playwright test` 无失败）
- 现有 43 个测试不受影响（无回归）
