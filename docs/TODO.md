# v0.1.1 待办清单

## Agent 核心

- [x] Supervisor 各 WF State 独立拆分（当前共用 SharedState）
- [x] Supervisor Pre-plan 检查点回评逻辑
- [x] Critique WF → 打回上游 WF 自动重注入循环
- [x] Extraction WF 增量分析（跳过已有笔记的论文）
- [x] Ideation WF 三步 CoT 完整实现
- [x] Publish WF Typst/Beamer PDF 编译输出
- [x] Publish WF ZIP 打包完整流程（文献+报告+代码+图表）

## Tools & Skills

- [ ] PubMed 检索 Tool
- [ ] DOI / Arxiv ID 直接导入 Tool
- [ ] ppt_generation Skill 完整渲染流程

## RAG Pipeline

- [ ] 语义切块策略优化（双栏/公式/表格场景）
- [ ] bge-reranker-v2 Rerank 集成
- [ ] RAG 召回指标评测与调优

## 后端 API / Services

- [ ] Quota 配额计费与限流执行
- [ ] 文件上传代理至 S3/MinIO (预签名 URL 完整链路)
- [ ] Agent 任务暂停/恢复/终止(Kill) API
- [ ] 站内异步任务通知（长耗时完成/异常）
- [ ] SSE 断线重连与消息补发

## 数据层

- [ ] Alembic 迁移版本管理规范化
- [ ] Document 状态机流转完善（解析中/就绪/失败/重试）
- [ ] 向量索引清理与过期策略

## 前端

- [ ] Canvas 编辑器 Tab 切换状态保持
- [ ] PDF 高亮定位联动（chunk → PDF 页码）
- [ ] Research Tab 结构化产物卡片展示
- [ ] Sandbox Tab 图表实时渲染
- [ ] Settings 页学科偏好配置
- [ ] Settings 页 BYOK (Bring Your Own Key) 配置
- [ ] Settings 页用量统计面板
- [ ] Workspace Dashboard 文档解析状态展示

## CI/CD & 部署

- [ ] CI 集成测试环境变量解耦
- [ ] Celery Worker 容器化部署
- [ ] Sandbox 镜像预构建与拉取策略

## 测试

- [ ] Workflow 子图集成测试补全
- [ ] RAG Pipeline 端到端测试
- [ ] HITL 交互流程 E2E 测试
- [ ] 前端 E2E 测试覆盖率提升



v0.2.0 待办清单

- [ ] 实现桌面端
