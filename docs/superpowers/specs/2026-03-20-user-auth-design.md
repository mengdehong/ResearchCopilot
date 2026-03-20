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
