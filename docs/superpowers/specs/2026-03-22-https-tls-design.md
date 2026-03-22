# HTTPS / TLS 配置设计

## 背景

ResearchCopilot 部署域名 `rc.wenmou.site`。服务器已有宿主机 Nginx + certbot 为其他项目提供 HTTPS，可直接复用。

当前问题：
- ResearchCopilot 尚未配置宿主机 Nginx 的 `rc.wenmou.site` 站点文件
- `config.py` 中三个 URL 字段均为 `http://localhost:5173`，导致生产环境 OAuth 失败

**内部 nginx 容器不处理 TLS**，复用宿主机已有代理体系。

## 架构

```
Internet
  │
  ▼
宿主机 Nginx :443  ← certbot --nginx 自动写入证书（Let's Encrypt）
  │  TLS 终止，代理到容器
  ▼
rc-nginx 容器 :80  ← 内部 HTTP，路由 frontend / backend / SSE / metrics
```

---

## 变更详情

### 1. DNS 记录（腾讯云控制台，手动）

在 `https://console.cloud.tencent.com/cns/detail/wenmou.site/records` 添加：

| 类型 | 主机记录 | 记录值 | TTL |
|---|---|---|---|
| A | rc | 服务器公网 IP | 600 |

---

### 2. `deployment/docker-compose.yml` — nginx 端口绑定

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "127.0.0.1:8080:80"   # 只绑定 loopback，不对外直接暴露
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

> 原来是 `80:80`，改为 `127.0.0.1:8080:80`。流量只能从宿主机 nginx 进来。

---

### 3. `deployment/nginx/nginx.conf` — 无需修改

内部容器 nginx 保持 HTTP 80 不变。宿主机 nginx 会通过 `X-Forwarded-Proto: https` 告知后端实际协议。

---

### 4. 宿主机 nginx 站点配置（手动操作）

新建 `/etc/nginx/conf.d/rc.wenmou.site.conf`，**只写 HTTP**，certbot 会自动补全 HTTPS：

```nginx
server {
    listen 80;
    server_name rc.wenmou.site;

    client_max_body_size 100m;   # 支持文件上传

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # SSE 流式响应：关闭 buffering
    location ~* /api/.*/runs/.*/stream$ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```

然后：

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d rc.wenmou.site   # certbot 自动写入 443 块 + 证书 + HTTP→HTTPS 重定向
```

---

### 5. `backend/core/config.py` — 修正生产默认值

```python
# 修改前
allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
oauth_redirect_base_url: str = "http://localhost:5173"
frontend_url: str = "http://localhost:5173"

# 修改后
allowed_origins: list[str] = [
    "https://rc.wenmou.site",
    "http://localhost:5173",
    "http://localhost:3000",
]
oauth_redirect_base_url: str = "https://rc.wenmou.site"
frontend_url: str = "https://rc.wenmou.site"
```

本地开发用 `.env` 覆盖：

```env
OAUTH_REDIRECT_BASE_URL=http://localhost:5173
FRONTEND_URL=http://localhost:5173
```

---
curl -sI https://rc.wenmou.site | grep Strict-Transport-Security

### 6. OAuth Provider 控制台（手动）

| Provider | 操作 |
|---|---|
| GitHub | OAuth App → Authorization callback URL → `https://rc.wenmou.site/auth/callback` |
| Google | Cloud Console → Credentials → Authorized redirect URIs → 添加 `https://rc.wenmou.site/auth/callback` |

---

## 完整操作顺序

```
1. 腾讯云 DNS 添加 A 记录 rc → 服务器 IP
2. docker-compose.yml 改端口 → 重启 docker compose
3. 宿主机 /etc/nginx/conf.d/rc.wenmou.site.conf 新建（HTTP 版）
4. sudo nginx -t && sudo systemctl reload nginx
5. sudo certbot --nginx -d rc.wenmou.site
6. config.py 修改默认值
7. OAuth 控制台改 callback URL
8. 验证
```

---

## 验证计划

```bash
## 变更详情

### 1. DNS 记录（腾讯云控制台，手动）

在 `https://console.cloud.tencent.com/cns/detail/wenmou.site/records` 添加：

| 类型 | 主机记录 | 记录值        | TTL |
| ---- | -------- | ------------- | --- |
| A    | rc       | 服务器公网 IP | 600 |

# HTTP → HTTPS 重定向（certbot 自动添加）
curl -I http://rc.wenmou.site
# 期望: 301 Moved Permanently + Location: https://...

# TLS 证书有效
curl -vI https://rc.wenmou.site 2>&1 | grep -E "subject|expire|SSL"

# HSTS header（certbot 写入）
curl -sI https://rc.wenmou.site | grep Strict-Transport-Security

# 宿主机 nginx 配置正确
nginx -t
```

OAuth 端到端：访问 `https://rc.wenmou.site`，点击 GitHub/Google 登录，确认 callback 成功。
