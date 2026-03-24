# 用户注册登录设计规格

> **目标**：为 Research Copilot 实现完整的用户认证系统，支持邮箱密码注册/登录 + GitHub/Google OAuth 社交登录。
> **日期**：2026-03-20

---

## 一、需求概述

### 核心功能
- 邮箱 + 密码注册（含邮箱验证）
- 邮箱 + 密码登录
- GitHub / Google OAuth 社交登录
- Access Token (30min) + Refresh Token (14天) 双 token 机制
- 密码重置（发邮件 → 重置）
- OAuth 账号与本地账号自动关联（邮箱已验证时）

### 不在范围内
- 微信 OAuth（架构预留扩展点，暂不实现）
- 多因素认证 (MFA)
- 用户管理后台

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React SPA)                         │
│  LoginPage ─── RegisterPage ─── ForgotPasswordPage ─── ResetPage   │
│       │              │                  │                   │       │
│       ▼              ▼                  ▼                   ▼       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              AuthProvider (Context + Token 管理)              │   │
│  │  - accessToken: memory    - refreshToken: httpOnly cookie    │   │
│  │  - 自动静默刷新 (token 过期前 2min)                           │   │
│  └──────────────────────────────────────────┬───────────────────┘   │
└─────────────────────────────────────────────┼───────────────────────┘
                                              │
         ┌────────────────────────────────────┼────────────────────┐
         │              FastAPI Backend                             │
         │                                                         │
         │  POST /api/auth/register      ← 邮箱密码注册            │
         │  POST /api/auth/verify-email  ← 验证邮箱                │
         │  POST /api/auth/login         ← 邮箱密码登录            │
         │  POST /api/auth/refresh       ← 刷新 access token      │
         │  POST /api/auth/logout        ← 清除 refresh token     │
         │  POST /api/auth/forgot-password ← 发送重置邮件          │
         │  POST /api/auth/reset-password  ← 重置密码              │
         │  GET  /api/auth/oauth/{provider}/authorize ← OAuth 跳转 │
         │  GET  /api/auth/oauth/{provider}/callback  ← OAuth 回调 │
         │  GET  /api/auth/me            ← (已有) 获取用户信息      │
         │  PUT  /api/auth/settings      ← (已有) 更新设置         │
         │                                                         │
         │  ┌───────────────────────────────────────────────────┐   │
         │  │ Services / Clients                                │   │
         │  │  AuthService   ─ 注册/登录/Token 签发核心逻辑     │   │
         │  │  EmailService  ─ 抽象接口 + Resend 实现           │   │
         │  │  OAuthProvider ─ 抽象接口 + GitHub/Google 实现    │   │
         │  └───────────────────────────────────────────────────┘   │
         └─────────────────────────────────────────────────────────┘
```

---

## 三、API 端点设计

### 3.1 邮箱密码注册

```
POST /api/auth/register
Request:  { email: str, password: str, display_name: str }
Response: { message: "验证邮件已发送" }
Status:   201 Created / 409 Conflict (邮箱已存在)
逻辑：
  1. 校验密码强度（≥8位，含字母+数字）
  2. 检查邮箱唯一性
  3. bcrypt 哈希密码，创建 User(email_verified=false, auth_provider="local")
  4. 签发 email_verify JWT (30min)，发验证邮件
```

### 3.2 邮箱验证

```
POST /api/auth/verify-email
Request:  { token: str }
Response: { message: "邮箱验证成功" }
Status:   200 OK / 400 Bad Request (token 无效/过期)
逻辑：解码 JWT(purpose=email_verify) → 标记 email_verified=true
```

### 3.3 邮箱密码登录

```
POST /api/auth/login
Request:  { email: str, password: str }
Response: { access_token: str, user: UserInfo }
          + Set-Cookie: refresh_token (httpOnly, Secure, SameSite=Lax, 14天)
Status:   200 OK / 401 Unauthorized / 403 Forbidden (邮箱未验证)
逻辑：
  1. 查找用户 → 验证密码 → 检查 email_verified
  2. 签发 access_token (30min) + refresh_token (14天)
  3. 存 refresh_token hash 到 RefreshToken 表
```

### 3.4 Token 刷新

```
POST /api/auth/refresh
Request:  Cookie 自动带 refresh_token
Response: { access_token: str }
Status:   200 OK / 401 Unauthorized (refresh token 无效/过期/已吊销)
逻辑：
  1. 从 cookie 读 refresh_token → 查 DB hash 匹配
  2. 检查未过期 & 未吊销
  3. 签发新 access_token
```

### 3.5 登出

```
POST /api/auth/logout
Request:  Cookie 自动带 refresh_token
Response: 204 No Content + Clear-Cookie
逻辑：标记 RefreshToken.revoked=true + 清除 cookie
```

### 3.6 忘记密码

```
POST /api/auth/forgot-password
Request:  { email: str }
Response: { message: "如果邮箱存在，重置邮件已发送" }
Status:   200 OK (无论邮箱是否存在，防枚举)
逻辑：查找用户 → 签发 password_reset JWT (30min) → 发重置邮件
```

### 3.7 重置密码

```
POST /api/auth/reset-password
Request:  { token: str, new_password: str }
Response: { message: "密码重置成功" }
Status:   200 OK / 400 Bad Request
逻辑：解码 JWT(purpose=password_reset) → 更新密码哈希 → 吊销该用户所有 refresh_token
```

### 3.8 OAuth 发起

```
GET /api/auth/oauth/{provider}/authorize
Response: 302 Redirect → GitHub/Google 授权页
逻辑：生成随机 state → 存 cookie(5min) → 构造授权 URL → 302 跳转
```

### 3.9 OAuth 回调

```
GET /api/auth/oauth/{provider}/callback?code=xxx&state=xxx
Response: 302 Redirect → 前端 /workspaces + Set-Cookie(refresh_token)
逻辑：
  1. 校验 state 防 CSRF
  2. 用 code 换 access_token → 拉用户信息(email, name, external_id)
  3. 查找已有用户 → 自动关联或新建
  4. 签发 JWT → 302 跳前端，URL 带 access_token 参数 + cookie 带 refresh_token
```

---

## 四、数据模型

### 4.1 User 模型变更

在现有 `User` 模型上扩展：

```python
class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # --- 现有字段 ---
    external_id: str           # OAuth 用户: "github:{id}" / "google:{id}"
                               # 邮箱用户: "local:{user_id}"
    email: str                 # 唯一索引
    display_name: str
    settings: dict             # JSONB

    # --- 新增字段 ---
    password_hash: str | None  # 邮箱用户有值，OAuth 用户为 None
    email_verified: bool       # 默认 False
    auth_provider: str         # "local" | "github" | "google"
```

### 4.2 新增 RefreshToken 表

```python
class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"

    user_id: uuid.UUID         # FK → users.id, indexed
    token_hash: str            # SHA-256(refresh_token)，不存明文
    expires_at: datetime       # 14 天后
    revoked: bool              # 默认 False，登出时设 True
    device_info: str | None    # User-Agent，可选，用于"管理登录设备"
```

### 4.3 Alembic 迁移

新增一个 migration 文件：
- `users` 表添加 `password_hash`, `email_verified`, `auth_provider` 字段
- 新建 `refresh_tokens` 表
- 现有用户 `auth_provider` 默认设为 `"local"`，`email_verified` 设为 `true`

---

## 五、服务层与 Clients 层

### 5.1 文件组织

```
backend/services/
├── auth_service.py           # 核心认证逻辑（纯函数为主）

backend/clients/
├── oauth/                    # OAuth Provider 抽象 + 实现
│   ├── base.py               # OAuthProvider 协议（Protocol）
│   ├── github.py             # GitHubOAuthProvider
│   └── google.py             # GoogleOAuthProvider
└── email/                    # 邮件服务抽象 + 实现
    ├── base.py               # EmailService 协议（Protocol）
    └── resend_client.py      # ResendEmailService
```

### 5.2 OAuthProvider 协议

```python
class OAuthUserInfo(TypedDict):
    external_id: str           # "github:12345" / "google:abc123"
    email: str
    display_name: str

class OAuthProvider(Protocol):
    provider_name: str

    def get_authorize_url(self, state: str, redirect_uri: str) -> str: ...
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo: ...
```

### 5.3 EmailService 协议

```python
class EmailService(Protocol):
    async def send_verification_email(self, to: str, token: str) -> None: ...
    async def send_password_reset_email(self, to: str, token: str) -> None: ...
```

---

## 六、前端设计

### 6.1 页面结构

```
/login              → LoginPage（左右分栏：左品牌区 + 右表单区）
/register           → RegisterPage（同上布局）
/verify-email       → VerifyEmailPage（验证结果页）
/forgot-password    → ForgotPasswordPage（输入邮箱表单）
/reset-password     → ResetPasswordPage（输入新密码表单）
```

所有认证页面使用 **左右分栏** 布局：
- **左侧**：品牌宣传区 — Logo + Slogan + 动态背景/插图
- **右侧**：表单区 — 登录/注册表单 + OAuth 按钮

### 6.2 文件组织

```
frontend/src/features/auth/
├── components/
│   ├── AuthLayout.tsx          # 左右分栏布局壳
│   ├── OAuthButtons.tsx        # GitHub + Google 登录按钮组
│   └── PasswordInput.tsx       # 带显示/隐藏切换的密码输入框
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── VerifyEmailPage.tsx
│   ├── ForgotPasswordPage.tsx
│   └── ResetPasswordPage.tsx
├── AuthProvider.tsx             # Context Provider + Token 管理
├── useAuth.ts                   # useAuth() hook（从 Context 取值）
└── auth.css
```

### 6.3 Token 管理

| Token         | 存储                               | 说明                                |
| ------------- | ---------------------------------- | ----------------------------------- |
| Access Token  | 内存 (AuthProvider state)          | 防 XSS，刷新页面后通过 refresh 恢复 |
| Refresh Token | httpOnly cookie（后端 Set-Cookie） | 前端 JS 完全不可读                  |

### 6.4 AuthProvider 核心逻辑

```
AuthProvider mount
  → isLoading = true（全屏 loading spinner）
  → POST /api/auth/refresh（cookie 自动带）
  → 成功 → 存 access_token + GET /api/auth/me → isAuthenticated = true
  → 失败 → isAuthenticated = false
  → isLoading = false

自动刷新定时器：
  → access_token 过期前 2 分钟自动 POST /refresh
  → 失败则标记 isAuthenticated = false → 路由守卫跳 /login
```

### 6.5 路由守卫

```
RootLayout               ← AuthProvider 在此注入
├── /login                ← GuestGuard（已登录 → 跳 /workspaces）
├── /register             ← GuestGuard
├── /verify-email         ← 公开
├── /forgot-password      ← 公开
├── /reset-password       ← 公开
└── AppLayout             ← AuthGuard（未登录 → 跳 /login）
    ├── /workspaces
    └── /workspaces/:id

AuthGuard: isLoading ? <Spinner/> : !isAuthenticated ? <Navigate to="/login"/> : <Outlet/>
GuestGuard: isAuthenticated ? <Navigate to="/workspaces"/> : <Outlet/>
```

### 6.6 API 层改造

现有 `api.ts` 改造：
- `accessToken` 从 AuthProvider 内存获取，不再用 localStorage
- 401 拦截器改为：尝试 refresh → 成功则重试原请求 → 仍失败则跳 /login
- 移除 `getToken()` / `setToken()` / `clearToken()`（localStorage 函数）

---

## 七、安全设计

### 7.1 安全清单

| 项目          | 措施                                                        |
| ------------- | ----------------------------------------------------------- |
| 密码存储      | bcrypt hash (cost=12)，不可逆                               |
| Access Token  | 内存存储，30min 过期，HS256 签名                            |
| Refresh Token | httpOnly + Secure + SameSite=Lax cookie，DB 存 SHA-256 hash |
| 验证/重置令牌 | JWT 30min 有效期，payload 带 `purpose` 字段区分用途         |
| OAuth state   | 随机 state 参数防 CSRF，存 cookie(5min) 校验                |
| 登录防暴力    | 速率限制（同 IP 5 次/分钟）via FastAPI middleware           |
| 密码要求      | 最少 8 位，至少包含字母和数字                               |
| CORS          | 仅允许前端域名 origin                                       |

### 7.2 OAuth 账号关联策略

当 OAuth 登录时发现同 email 的本地账号：
- **email_verified = true** → 自动关联，合并为同一用户，更新 `external_id`
- **email_verified = false** → 拒绝关联，提示"此邮箱已注册但未验证，请先验证邮箱"

当本地注册时发现同 email 的 OAuth 账号：
- 返回 409 Conflict，提示"此邮箱已通过 {provider} 登录，请使用 {provider} 登录"

---

## 八、配置与依赖

### 8.1 新增环境变量

```env
# --- Auth (现有) ---
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256

# --- Auth (新增) ---
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14

# --- OAuth ---
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
OAUTH_REDIRECT_BASE_URL=http://localhost:5173

# --- Email ---
RESEND_API_KEY=re_xxx
EMAIL_FROM=noreply@researchcopilot.com
FRONTEND_URL=http://localhost:5173
```

### 8.2 新增 Python 依赖

```
bcrypt          # 密码哈希
httpx           # OAuth API 调用（已存在则无需新增）
resend          # 邮件发送
```

### 8.3 Settings 扩展

在 `backend/core/config.py` 的 `Settings` 类中新增上述配置字段。

---

## 九、影响范围

### 需修改的现有文件

| 文件                              | 变更                                                         |
| --------------------------------- | ------------------------------------------------------------ |
| `backend/models/user.py`          | 新增 `password_hash`, `email_verified`, `auth_provider` 字段 |
| `backend/api/routers/auth.py`     | 新增注册/登录/OAuth/密码重置等端点                           |
| `backend/api/schemas/auth.py`     | 新增请求/响应 schemas                                        |
| `backend/api/dependencies.py`     | token 提取逻辑适配（现有逻辑基本不变）                       |
| `backend/core/config.py`          | 新增 OAuth/Email/Token 配置字段                              |
| `frontend/src/lib/api.ts`         | 移除 localStorage，改为接受内存 token                        |
| `frontend/src/app/AppLayout.tsx`  | 使用 AuthGuard 替代现有占位逻辑                              |
| `frontend/src/app/router.tsx`     | 新增 auth 页面路由                                           |
| `frontend/src/app/RootLayout.tsx` | 注入 AuthProvider                                            |

### 需新建的文件

| 文件                                     | 说明                             |
| ---------------------------------------- | -------------------------------- |
| `backend/models/refresh_token.py`        | RefreshToken ORM                 |
| `backend/services/auth_service.py`       | 认证核心逻辑                     |
| `backend/clients/oauth/base.py`          | OAuthProvider Protocol           |
| `backend/clients/oauth/github.py`        | GitHub OAuth 实现                |
| `backend/clients/oauth/google.py`        | Google OAuth 实现                |
| `backend/clients/email/base.py`          | EmailService Protocol            |
| `backend/clients/email/resend_client.py` | Resend 实现                      |
| `alembic/versions/xxx_add_auth.py`       | 数据库迁移                       |
| `frontend/src/features/auth/`            | 整个前端 auth 模块（~10 个文件） |
