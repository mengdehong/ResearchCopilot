# Research Copilot — 产品级上线差距分析


## P0 — 必须修复（上线阻断项）



### 🔴 2.3 HTTPS / TLS 未配置

- `nginx.conf` 只有 HTTP 80 端口
- 无 SSL 证书配置
- 无 HTTP→HTTPS 重定向
- OAuth 回调 URL 使用 `http://localhost:5173`

**建议**：部署方案须包含 TLS 终端（Nginx + Let's Encry

## 三、P1 — 上线前必须完善


### 🟡 3.3 Agent SSE 流的健壮性

- SSE `event_generator` 中异常会导致流中断但客户端不一定能感知
- 没有心跳机制（keep-alive），长时间无事件时连接可能被代理/LB 断开
- 缺少事件 ID 持久化，断线重连可能丢失事件

---

### 🟡 3.4 Sandbox 安全加固

| 项目            | 当前状态 | 建议                                      |
| --------------- | -------- | ----------------------------------------- |
| 磁盘限制        | 无       | 添加 `storage_opt` 限制或 tmpfs           |
| PID 限制        | 无       | `pids_limit=100` 防止 fork bomb           |
| 只读文件系统    | 否       | `read_only=True` + tmpfs for `/workspace` |
| seccomp profile | 默认     | 使用更严格的 seccomp/AppArmor             |
| Privileged 检查 | 未校验   | 确保 `privileged=False`                   |

# 四、P2 — 上线后持续改进

### 🔵 4.1 性能优化

| 项目          | 建议                                                     |
| ------------- | -------------------------------------------------------- |
| RAG Embedding | `sentence-transformers` 加载在单线程中，需换成 GPU async |
| DB N+1        | 部分查询（如 workspace 列表）可能存在 N+1                |
| SSE 连接池    | 大量并发用户时 SSE 长连接会占用 worker 线程              |
| 前端构建      | 无 code splitting/动态导入配置                           |

---

### 🔵 4.2 可用性 & 容错

| 项目           | 建议                                       |
| -------------- | ------------------------------------------ |
| 断路器         | LLM Gateway 无断路器，连续失败会重试到耗尽 |
| 连接池健康检查 | Redis/PG 连接池无主动健康检查              |
| 多区部署       | 无 K8s manifest / Terraform                |
| 蓝绿/灰度部署  | 无                                         |

---


### 🔵 4.4 数据安全与合规

| 项目             | 状态                                                 |
| ---------------- | ---------------------------------------------------- |
| GDPR 数据删除    | ❌ 无"删除我的数据"功能                               |
| 数据加密 at rest | ❌ S3/MinIO 和 PG 均为明文                            |
| 审计日志         | ❌ 核心操作（删除工作区、运行代码）无审计记录         |
| Cookie 安全属性  | ⚠️ refresh token 用了 HttpOnly 但未见 Secure/SameSite |
| CSP 头           | ❌ 未配置 Content-Security-Policy                     |
| 输入校验         | ⚠️ Pydantic schema 有基础校验，但缺少长度/注入防护    |
