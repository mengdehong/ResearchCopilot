# RAG Pipeline 架构设计

> Research Copilot 的检索增强生成管道，负责学术文献从 PDF 到可检索知识的全链路转换。

## 一、设计目标

- **精确溯源**：任何检索结果可追溯到原 PDF 的具体页面和位置
- **语义完整**：chunk 保持学术论文的结构语义，不粗暴按 token 截断
- **跨文档推理**：支持"对比 5 篇论文方法论"等跨文献问答
- **渐进式架构**：MVP 先做方案 B（分表），后续可平滑演进到关系图谱

---

## 二、数据模型（PostgreSQL + pgvector）

按内容类型分表，每类内容有精确的 schema。所有向量列使用 pgvector 的 `vector` 类型。

### 2.1 核心表结构

```
┌──────────────────────────────────────────────────────────────────┐
│                        documents (文档元数据)                     │
│  id | title | authors | year | source | doi | workspace_id      │
│  upload_status | parse_status | created_at                       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ document_id (FK)
      ┌──────────┬───────────┼───────────┬───────────┬────────────┐
      ▼          ▼           ▼           ▼           ▼            ▼
┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│doc_      ││paragraphs││tables    ││figures   ││equations ││section_  │
│summaries ││          ││          ││          ││          ││headings  │
│          ││          ││          ││          ││          ││          │
│文档级索引││正文段落  ││表格三层  ││图表      ││公式      ││章节导航  │
└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘

+ references (结构化引用，不做 embedding)
```

### 2.2 各表字段设计

#### `documents` — 文档元数据

| 字段             | 类型        | 说明                                     |
| ---------------- | ----------- | ---------------------------------------- |
| id               | UUID        | 主键                                     |
| workspace_id     | UUID        | FK → workspaces，租户隔离                |
| title            | TEXT        | 论文标题                                 |
| authors          | JSONB       | 作者列表 `["Author A", "Author B"]`      |
| year             | INT         | 发表年份                                 |
| source           | TEXT        | 来源（arxiv / pubmed / upload）          |
| doi              | TEXT        | DOI 标识，UNIQUE                         |
| abstract_text    | TEXT        | 原始摘要文本                             |
| file_path        | TEXT        | OSS/S3 原始 PDF 路径                     |
| parse_status     | ENUM        | `pending / parsing / completed / failed` |
| include_appendix | BOOL        | 用户选择是否保留附录                     |
| created_at       | TIMESTAMPTZ | 入库时间                                 |

#### `doc_summaries` — 文档级索引（用于"找哪几篇最相关"）

| 字段         | 类型        | 说明                                                               |
| ------------ | ----------- | ------------------------------------------------------------------ |
| id           | UUID        | 主键                                                               |
| document_id  | UUID        | FK → documents                                                     |
| content_type | ENUM        | `abstract / conclusion / contributions / limitations / discussion` |
| content_text | TEXT        | 原始文本                                                           |
| embedding    | vector(dim) | 向量表示                                                           |
| tsv          | tsvector    | 全文检索索引                                                       |

> **设计意图**：Abstract + Conclusion + Limitations + Discussion + Contributions 分别入库，成对处理。文档级检索时合并召回。

#### `paragraphs` — 正文段落（证据级检索的主力）

| 字段         | 类型        | 说明                                       |
| ------------ | ----------- | ------------------------------------------ |
| id           | UUID        | 主键                                       |
| document_id  | UUID        | FK → documents                             |
| section_path | TEXT        | 章节路径，如 `"3. Methods > 3.2 Training"` |
| chunk_index  | INT         | 段落在文档中的顺序号                       |
| content_text | TEXT        | 段落原文                                   |
| page_numbers | INT[]       | 所在 PDF 页码（用于溯源高亮）              |
| bbox         | JSONB       | MinerU 输出的页面坐标（用于精确定位）      |
| embedding    | vector(dim) | 向量表示                                   |
| tsv          | tsvector    | 全文检索索引                               |

#### `tables` — 表格三层表示

| 字段         | 类型        | 说明                                                              |
| ------------ | ----------- | ----------------------------------------------------------------- |
| id           | UUID        | 主键                                                              |
| document_id  | UUID        | FK → documents                                                    |
| section_path | TEXT        | 所在章节路径                                                      |
| table_title  | TEXT        | 表格标题（caption）                                               |
| page_number  | INT         | 所在页码                                                          |
| raw_data     | JSONB       | **原始层**：行列名、单元格值、脚注                                |
| summary_text | TEXT        | **语义层**：LLM 生成的语义化摘要                                  |
| schema_data  | JSONB       | **Schema 层**：`{topic, entities, best_method, best_metric, ...}` |
| embedding    | vector(dim) | 基于 summary_text 生成                                            |
| tsv          | tsvector    | 基于 summary_text + table_title                                   |

> **三层用途**：raw_data → 精确回显/数值校验/导出；summary_text → 检索和问答；schema_data → 过滤和路由。

#### `figures` — 图表

| 字段         | 类型        | 说明                             |
| ------------ | ----------- | -------------------------------- |
| id           | UUID        | 主键                             |
| document_id  | UUID        | FK → documents                   |
| section_path | TEXT        | 所在章节                         |
| caption_text | TEXT        | 图表说明文字                     |
| context_text | TEXT        | 上下文引用段落（提到该图的正文） |
| image_path   | TEXT        | 图片文件 OSS 路径                |
| page_number  | INT         | 所在页码                         |
| embedding    | vector(dim) | 基于 caption + context 生成      |

#### `equations` — 数学公式

| 字段           | 类型        | 说明                                       |
| -------------- | ----------- | ------------------------------------------ |
| id             | UUID        | 主键                                       |
| document_id    | UUID        | FK → documents                             |
| section_path   | TEXT        | 所在章节                                   |
| latex_text     | TEXT        | LaTeX 原文                                 |
| context_text   | TEXT        | 公式前后的解释性段落                       |
| equation_label | TEXT        | 公式编号（如 Eq. 3），可为空               |
| page_number    | INT         | 所在页码                                   |
| embedding      | vector(dim) | 基于 context_text 生成（公式本身不 embed） |

#### `section_headings` — 章节导航（用于 Query Routing）

| 字段         | 类型        | 说明                    |
| ------------ | ----------- | ----------------------- |
| id           | UUID        | 主键                    |
| document_id  | UUID        | FK → documents          |
| level        | INT         | 层级（1=H1, 2=H2, ...） |
| heading_text | TEXT        | 标题文本                |
| parent_id    | UUID        | FK → self，构成章节树   |
| page_number  | INT         | 起始页码                |
| embedding    | vector(dim) | 向量表示                |

#### `references` — 参考文献（结构化存储，不做 Embedding）

| 字段               | 类型 | 说明                                 |
| ------------------ | ---- | ------------------------------------ |
| id                 | UUID | 主键                                 |
| document_id        | UUID | FK → documents（引用方）             |
| ref_index          | INT  | 文中引用编号 `[1]`                   |
| ref_title          | TEXT | 被引论文标题                         |
| ref_authors        | TEXT | 被引作者                             |
| ref_year           | INT  | 被引年份                             |
| ref_doi            | TEXT | 被引 DOI（可能为空）                 |
| linked_document_id | UUID | FK → documents（若被引论文也在库中） |

---

## 三、Ingestion Pipeline（离线异步管道）

### 3.1 管道架构

```
用户上传 PDF / Discovery WF 自动抓取
         │
         ▼
┌─ Stage 1: 解析 ──────────────────────────────────┐
│  MinerU GPU Worker                                │
│  PDF → 结构化 Markdown + 版面坐标(bbox) + 图片    │
│  输出：ParsedDocument（含完整结构信息）            │
└──────────────────────────┬────────────────────────┘
                           │
                           ▼
┌─ Stage 2: 内容分类与提取 ─────────────────────────┐
│  规则引擎（不需要 LLM）                           │
│  按论文结构识别各内容类型：                        │
│  - Abstract / Conclusion / Discussion / Limitations│
│  - 正文段落（按结构边界切块）                      │
│  - 表格（提取原始结构 raw_data）                   │
│  - 图表（提取 caption + 上下文）                   │
│  - 公式（LaTeX + 上下文）                          │
│  - 章节标题树                                      │
│  - 参考文献列表                                    │
│  - 排版噪音（页码/页眉） → 丢弃                   │
│  - 附录 → 按用户配置保留或跳过                     │
└──────────────────────────┬────────────────────────┘
                           │
                           ▼
┌─ Stage 3: LLM 语义增强 ──────────────────────────┐
│  LLM Worker（调用配置的模型）                      │
│  - 表格 → 生成 summary_text + schema_data         │
│  - Contributions → 提取 bullet list                │
│  - （可选）超长段落的关键句摘要                     │
│  批量处理，单文档所有表格合并为一次 LLM 请求       │
└──────────────────────────┬────────────────────────┘
                           │
                           ▼
┌─ Stage 4: Embedding + 入库 ───────────────────────┐
│  Embedding Worker                                  │
│  - 统一多语言 Embedding 模型编码所有 text 字段     │
│  - 生成 tsvector 全文检索索引                      │
│  - 按内容类型写入对应的分表                        │
│  - 更新 documents.parse_status = completed         │
└───────────────────────────────────────────────────┘
```

### 3.2 Chunking 规则

| 内容类型              | 切块策略                           | 说明                                                            |
| --------------------- | ---------------------------------- | --------------------------------------------------------------- |
| 正文段落              | 按论文结构边界（Paragraph）切块    | 一个自然段 = 一个 chunk。若单段 > 1024 tokens，在句子边界处分割 |
| Abstract / Conclusion | 整体作为一个 chunk                 | 信息密度高，不切割                                              |
| 表格                  | 整表为一个 chunk                   | summary_text 用于 embedding                                     |
| 图表                  | caption + context 合并为一个 chunk | 提供完整上下文                                                  |
| 公式                  | context_text 作为 chunk            | 公式本身不单独 embed，LaTeX 只做存储                            |
| 章节标题              | 每个 heading 独立一个 chunk        | 用于路由而非深度检索                                            |

### 3.3 失败处理

- MinerU 解析失败 → 降级为纯文本提取（PyMuPDF fallback），标记 `parse_quality = degraded`
- LLM 语义增强失败 → 跳过 Stage 3，表格仅存 raw_data + caption，无 summary
- Embedding 失败 → 重试 3 次，仍失败则标记该 chunk `embed_status = failed`，不阻塞其他 chunk

---

## 四、Retrieval Pipeline（在线检索）

### 4.1 三阶段召回流程

```
用户查询（中文/英文）
         │
         ▼
┌─ Pre-processing ─────────────────────────────────┐
│  1. LLM Query Rewriting                           │
│     - 中文 → 英文学术术语转写                      │
│     - 扩展同义词（如 "注意力机制" → "attention")   │
│     - 输出：rewritten_query + original_query       │
│                                                    │
│  2. Query Routing                                  │
│     - LLM 判断查询意图分类：                       │
│       · document_level（找哪些论文相关）            │
│       · evidence_level（找具体段落/表格/公式）       │
│       · cross_doc（跨文档对比）                     │
│     - 确定需要查哪些表                             │
└──────────────────────────┬────────────────────────┘
                           │
                           ▼
┌─ Stage 1: 粗召回 ────────────────────────────────┐
│  并行执行：                                        │
│  A. 向量检索：pgvector cosine similarity           │
│     → 目标表中取 top-K₁ 候选                       │
│  B. 关键词检索：PostgreSQL tsvector/tsquery         │
│     → 目标表中取 top-K₂ 候选                       │
│  融合：RRF (Reciprocal Rank Fusion) 合并排序       │
│  输出：top-K 候选 chunks（K ≈ 30-50）              │
└──────────────────────────┬────────────────────────┘
                           │
                           ▼
┌─ Stage 2: 精排 ──────────────────────────────────┐
│  Cross-Encoder Reranker（如 bge-reranker-v2）      │
│  对 (query, chunk_text) pair 逐一打分              │
│  输出：top-N 最终结果（N ≈ 5-10）                  │
└──────────────────────────┬────────────────────────┘
                           │
                           ▼
┌─ Post-processing ────────────────────────────────┐
│  - 附加溯源元数据：document_title, page_number,    │
│    section_path, bbox                              │
│  - 若命中 table：附带 raw_data 用于精确回显        │
│  - 若命中 equation：附带 LaTeX 用于公式渲染        │
│  - 去重（同文档同页面的重叠结果合并）               │
│  输出 → Agent (Extraction WF / 其他 WF)            │
└───────────────────────────────────────────────────┘
```

### 4.2 跨文档对比查询

当 Query Router 判断为 `cross_doc` 意图时：
1. 先查 `doc_summaries` 找到最相关的 N 篇文档
2. 在这 N 篇文档范围内并行查 `paragraphs` + `tables`
3. 将结果按 `document_id` 分组，交给 LLM 做对比分析

### 4.3 检索参数默认值

| 参数                    | 默认值 | 说明                         |
| ----------------------- | ------ | ---------------------------- |
| 粗召回 top-K₁（向量）   | 30     | 向量检索候选数               |
| 粗召回 top-K₂（关键词） | 30     | 全文检索候选数               |
| RRF k 参数              | 60     | 标准 RRF 融合常数            |
| 精排 top-N              | 8      | 最终返回给 Agent 的 chunk 数 |

---

## 五、与 Agent Workflow 的集成

| Workflow       | RAG 交互方式                                                                         |
| -------------- | ------------------------------------------------------------------------------------ |
| **Discovery**  | 用户 HITL 勾选论文后，通过 BFF document service 触发 Ingestion Pipeline 异步解析入库 |
| **Extraction** | 定向 RAG 召回：按指定文档 ID 过滤，做证据级检索；支持增量分析（跳过已有笔记的论文）  |
| **Ideation**   | 跨文档 RAG：不限文档范围，做语义理解型检索                                           |
| **Critique**   | 溯源验证：检索原文段落验证 Agent 生成内容的引用准确性                                |
| **Publish**    | 引用角标：查 references 表获取结构化引用信息                                         |

> **注意**：Ingestion 触发统一通过 BFF document service，无论论文来自 Discovery 搜索还是用户上传，入口一致。

---

## 六、技术选型汇总

| 组件            | 选择                    | 理由                                    |
| --------------- | ----------------------- | --------------------------------------- |
| PDF 解析        | MinerU (GPU)            | 双栏/公式/表格精准还原，输出结构化 bbox |
| 向量数据库      | pgvector                | 与业务数据同库，分表方案原生支持        |
| 全文检索        | PostgreSQL tsvector     | 零额外依赖，与向量检索同库同查询        |
| Embedding 模型  | bge-m3（推荐）          | 多语言、高维度、学术场景表现优秀        |
| Reranker        | bge-reranker-v2（推荐） | 跨语言 cross-encoder，精排效果好        |
| 异步任务        | Celery + Redis          | 与架构文档一致                          |
| LLM（语义增强） | Provider-agnostic       | 复用 llm_gateway.py 统一封装            |
