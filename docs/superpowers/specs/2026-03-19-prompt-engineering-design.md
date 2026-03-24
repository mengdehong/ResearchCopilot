# Prompt 工程规范

> Agent 运行时所有 Prompt 的组织、存储、加载、版本管理与自动优化策略。

---

## 一、Prompt 存储与目录结构

### 1.1 设计决策

采用 **YAML baseline + DB 覆盖层** 模式：

- YAML 文件随代码提交，是所有环境的 source of truth
- DB 只存覆盖/优化版本（人工微调或 GEPA 自动优化结果）
- 回滚 = 将 DB 覆盖设为 `active=false`，自动降级回 YAML 版

### 1.2 目录结构

```
backend/agent/prompts/
├── _loader.py                    # PromptLoader：YAML → DB override → 最终 prompt
├── supervisor/
│   ├── skeleton.yaml             # Supervisor 通用骨架（角色、路由规则、输出格式）
│   └── disciplines/              # 学科 snippet（按学科独立文件）
│       ├── computer_science.yaml
│       ├── biology.yaml
│       ├── physics.yaml
│       └── ...
├── discovery/
│   └── expand_query.yaml         # 查询扩展
├── extraction/
│   ├── generate_notes.yaml       # 精读笔记生成
│   ├── cross_compare.yaml        # 跨文档对比
│   └── build_glossary.yaml       # 术语表构建
├── ideation/
│   ├── gap_summarize.yaml        # CoT 第 1 步：归纳总结
│   ├── gap_compare.yaml          # CoT 第 2 步：交叉对比
│   ├── gap_evaluate.yaml         # CoT 第 3 步：深化评估
│   └── generate_designs.yaml     # 实验方案生成
├── execution/
│   ├── generate_code.yaml        # 代码生成
│   └── reflect.yaml              # 失败反思
├── critique/
│   ├── supporter.yaml            # 蓝方（支持者）独立 prompt
│   ├── critic.yaml               # 红方（批评者）独立 prompt
│   └── judge.yaml                # 裁决者 prompt
└── publish/
    ├── assemble_outline.yaml     # 大纲组装
    └── generate_markdown.yaml    # Markdown 报告生成
```

Skill 专属 Prompt 放在各 Skill 目录内（已有规范）：

```
backend/agent/skills/arxiv_search/prompts/query_expand.yaml
backend/agent/skills/ppt_generation/prompts/slide_schema.yaml
```

### 1.3 YAML 模板格式

每个 Prompt 文件统一 5 个字段：

```yaml
name: expand_query                    # 唯一标识，与文件路径对应
version: "1.0.0"                      # 语义化版本号
description: "将用户查询扩展为多组搜索词"

system: |
  你是一位学术检索专家。
  给定一个研究主题，生成 3-5 个语义相关的搜索查询。
  包含同义词、上位/下位概念、英文变体。

  当前学科：{discipline}

user_template: |
  用户研究主题：{topic}
  时间范围：{time_range}

  请生成扩展查询列表。
```

**字段说明**：

| 字段            | 必填 | 说明                                    |
| --------------- | ---- | --------------------------------------- |
| `name`          | ✅    | 唯一标识，格式 `wf_name/node_name`      |
| `version`       | ✅    | 语义化版本，GEPA 优化后自动递增 patch   |
| `description`   | ✅    | 人类可读描述，用于可观测性和管理界面    |
| `system`        | ✅    | System prompt 内容，支持 `{var}` 占位符 |
| `user_template` | ❌    | User message 模板，部分节点不需要       |

**占位符约定**：

- `{discipline}` — 学科名称，由 PromptLoader 从 State 注入
- `{discipline_snippet}` — 学科 snippet 全文，仅 Supervisor 骨架使用
- `{available_skills}` — 当前注册的 Skill 列表，仅 Supervisor 使用
- 其余占位符由各节点在调用时传入（如 `{topic}`、`{code}`、`{error}`）

---

## 二、PromptLoader — 加载机制

### 2.1 加载流程

```
PromptLoader.load("critique/critic", discipline="computer_science")
    │
    ├─ 1) 读 YAML: prompts/critique/critic.yaml
    ├─ 2) 查 DB:   SELECT content FROM prompt_overrides
    │              WHERE name='critique/critic' AND active=true
    │              → 有覆盖则替换 system/user_template 字段，无则用 YAML 原文
    ├─ 3) 注入学科 snippet（仅 Supervisor）
    └─ 4) 返回 PromptTemplate 对象（变量渲染延迟到调用时）
```

### 2.2 DB 覆盖表

```sql
CREATE TABLE prompt_overrides (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,            -- 'critique/critic'
    version     TEXT NOT NULL,            -- '1.0.0-gepa-v3'
    content     JSONB NOT NULL,           -- {"system": "...", "user_template": "..."}
    source      TEXT NOT NULL DEFAULT 'manual',  -- 'manual' | 'gepa'
    score       FLOAT,                    -- GEPA 优化评分（source='gepa' 时有值）
    active      BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 同一 name 只允许一条 active=true
CREATE UNIQUE INDEX idx_prompt_active ON prompt_overrides (name) WHERE active;
```

### 2.3 核心 API

```python
@dataclass(frozen=True)
class PromptTemplate:
    """加载后的 Prompt 模板。变量渲染延迟到 render() 调用时。"""
    name: str
    version: str
    system: str
    user_template: str | None
    source: str            # 'yaml' | 'manual' | 'gepa'

    def render(self, **kwargs: str) -> tuple[str, str | None]:
        """渲染占位符，返回 (system_content, user_content)。"""
        system = self.system.format(**kwargs)
        user = self.user_template.format(**kwargs) if self.user_template else None
        return system, user


class PromptLoader:
    """Prompt 加载器：YAML baseline → DB 覆盖 → 模板对象。"""

    def __init__(self, prompts_dir: Path, db_session: AsyncSession) -> None:
        self._prompts_dir = prompts_dir
        self._db = db_session

    async def load(self, name: str, discipline: str | None = None) -> PromptTemplate:
        """按 name 加载 Prompt，DB 覆盖优先。

        Args:
            name: Prompt 标识，如 'critique/critic'
            discipline: 学科名称，仅 Supervisor 骨架需要

        Returns:
            渲染前的 PromptTemplate 对象
        """
        yaml_data = self._load_yaml(name)
        db_override = await self._query_active_override(name)

        if db_override:
            system = db_override["system"]
            user_template = db_override.get("user_template", yaml_data.get("user_template"))
            source = db_override["source"]
            version = db_override["version"]
        else:
            system = yaml_data["system"]
            user_template = yaml_data.get("user_template")
            source = "yaml"
            version = yaml_data["version"]

        # Supervisor 骨架注入学科 snippet
        if discipline and "{discipline_snippet}" in system:
            snippet = self._load_discipline_snippet(discipline)
            system = system.replace("{discipline_snippet}", snippet)

        return PromptTemplate(
            name=name, version=version,
            system=system, user_template=user_template,
            source=source,
        )
```

### 2.4 节点调用示例

```python
async def expand_query(state: DiscoveryState) -> dict:
    """Discovery WF：LLM 扩展查询词。"""
    prompt = await prompt_loader.load("discovery/expand_query")
    system_content, user_content = prompt.render(
        discipline=state["discipline"],
        topic=state["messages"][-1].content,
        time_range="2024-01-01:2025-03-01",
    )

    result = await llm.ainvoke([
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ])

    queries = parse_query_list(result.content)
    return {"search_queries": queries}
```

---

## 三、Supervisor System Prompt 设计

### 3.1 设计决策

采用 **骨架 + 学科 snippet 注入** 模式：

- 通用骨架定义角色、路由规则、输出格式约束——所有学科共用
- 学科差异仅体现在「领域知识 + 术语偏好」snippet 注入
- GEPA 可分别优化骨架和各学科 snippet

### 3.2 骨架模板

`prompts/supervisor/skeleton.yaml`:

```yaml
name: supervisor_skeleton
version: "1.0.0"
description: "Supervisor 主控调度器系统提示词骨架"

system: |
  # 角色
  你是 Research Copilot 的主控调度器（Supervisor）。
  你的职责是理解用户的研究意图，规划执行路径，将任务分配给专家 Workflow。

  # 可用 Workflow
  | 名称       | 职责     | 适用场景                              |
  | ---------- | -------- | ------------------------------------- |
  | discovery  | 寻源初筛 | 检索论文、提取 Meta、触发异步解析     |
  | extraction | 深度精读 | RAG 召回、跨文档对比、构建术语表      |
  | ideation   | 实验推演 | Research Gap 分析、实验方案、评估指标 |
  | execution  | 沙盒验证 | 代码生成、Docker 执行、Debug 重试     |
  | critique   | 模拟审稿 | 红蓝对抗、逻辑检测、结构化反馈        |
  | publish    | 报告交付 | Markdown 报告、PPTX 渲染、ZIP 打包    |

  # 可直接调用的 Skill
  {available_skills}

  # 路由决策规则
  1. 用户意图明确指向单一 WF → mode=single，直接路由
  2. 用户任务涉及多阶段 → mode=plan，输出完整执行计划
  3. 意图模糊或有多种可能解读 → 向用户确认意图再决策，不猜测
  4. 能用 Skill 直接解决的简单任务 → 不走 Workflow
  5. 每个计划步骤必须有明确的 objective 和 success_criteria

  # 学科上下文
  {discipline_snippet}

  # 输出要求
  严格按照 RouteDecision schema 输出 JSON。
  reasoning 字段必须包含决策理由（用于前端 CoT 展示和可观测性日志）。
```

### 3.3 学科 snippet 规范

`prompts/supervisor/disciplines/computer_science.yaml`:

```yaml
discipline: computer_science
display_name: "计算机科学"

snippet: |
  ## 领域知识
  - 核心会议：NeurIPS, ICML, ICLR, ACL, CVPR, AAAI, KDD
  - 核心期刊：JMLR, TPAMI, TACL
  - 检索偏好：优先 arXiv，辅以 Semantic Scholar 引用数据
  - 评价维度：方法创新性、实验充分性、可复现性、理论贡献
  - 常见研究范式：提出新模型/新方法 → Baseline 对比 → 消融实验 → 分析讨论

  ## 术语偏好
  - 使用英文术语原文，不强制翻译（如 Attention、Transformer、Fine-tuning）
  - 数学公式用 LaTeX 格式
  - 代码示例默认 Python
```

`prompts/supervisor/disciplines/biology.yaml`:

```yaml
discipline: biology
display_name: "生物学"

snippet: |
  ## 领域知识
  - 核心期刊：Nature, Science, Cell, PNAS, Nature Methods
  - 核心数据库：PubMed, UniProt, GenBank, PDB
  - 检索偏好：优先 PubMed，辅以 Google Scholar
  - 评价维度：实验设计严谨性、统计显著性、可重复性、临床/应用价值
  - 常见研究范式：假设驱动 → 实验验证 → 统计分析 → 机制解释

  ## 术语偏好
  - 基因/蛋白质名使用标准命名（如 BRCA1、p53）
  - 物种名使用拉丁文斜体（如 *Homo sapiens*）
  - 统计结果需标注 p-value 和置信区间
```

### 3.4 新增学科的流程

添加新学科仅需一个文件：

1. 创建 `prompts/supervisor/disciplines/{discipline}.yaml`
2. 填写 `discipline`、`display_name`、`snippet` 三个字段
3. 在用户设置中添加该学科选项

无需修改骨架、无需修改代码。学科 snippet 的 GEPA 优化也完全独立。

---

## 四、WF 关键节点 Prompt 设计

### 4.1 设计原则

| 原则           | 说明                                                              |
| -------------- | ----------------------------------------------------------------- |
| **单一职责**   | 每个 Prompt 文件对应一个节点的一次 LLM 调用，不混合多个任务       |
| **结构化输出** | 需要程序处理的输出一律用 `with_structured_output()`，不做文本解析 |
| **学科无关**   | 节点级 Prompt 不含学科硬编码，通过 `{discipline}` 占位符注入      |
| **可独立优化** | 每个 Prompt 文件是 GEPA 的最小优化单元                            |

### 4.2 Discovery — 查询扩展

**节点**：`expand_query`
**模式**：输入→变换→输出（纯函数型，最简单）

```yaml
name: discovery/expand_query
version: "1.0.0"
description: "将用户研究主题扩展为多组语义相关的搜索查询"

system: |
  你是一位学术检索专家，专精 {discipline} 领域。

  任务：将用户给出的研究主题扩展为 3-5 个搜索查询。

  扩展策略：
  1. 同义词替换（如 "大语言模型" ↔ "LLM" ↔ "Large Language Model"）
  2. 上位/下位概念（如 "Attention" → "Multi-Head Attention" / "Self-Attention"）
  3. 相关方法名（如 "RAG" → "Retrieval-Augmented Generation"）
  4. 跨语言变体（中英文关键词）

  要求：
  - 每个查询独立可用于学术搜索引擎
  - 覆盖面尽量广，但保持与原主题相关
  - 优先使用该领域的标准术语

user_template: |
  研究主题：{topic}
  时间范围偏好：{time_range}
```

**GEPA 评估指标**：扩展查询的检索召回率（用历史查询-论文对验证）。

### 4.3 Critique — 红蓝对抗（三方独立调用）

**设计决策**：蓝方（支持者）、红方（批评者）、裁决者各有独立 system prompt，分别调用 LLM。

#### 蓝方 — 支持者

```yaml
name: critique/supporter
version: "1.0.0"
description: "模拟审稿支持者角色，从正面评价研究产出物"

system: |
  你是一位资深学术审稿人，扮演「支持者」角色。

  任务：对提交的研究产出物进行正面评价。

  评价维度：
  1. 方法论的合理性和创新性
  2. 实验设计的完整性
  3. 论据的充分性和逻辑连贯性
  4. 对现有工作的充分引用和定位
  5. 结论的可靠性

  要求：
  - 客观公正，不盲目吹捧
  - 指出真正的优势和贡献
  - 用学术评审的专业语言
  - 给出具体的支持理由，而非笼统肯定

user_template: |
  ## 审查目标
  产出阶段：{target_workflow}

  ## 待审查内容
  {content_to_review}
```

#### 红方 — 批评者

```yaml
name: critique/critic
version: "1.0.0"
description: "模拟审稿批评者角色，从质疑角度审查研究产出物"

system: |
  你是一位严格的学术审稿人，扮演「批评者」角色。

  任务：对提交的研究产出物进行严格质疑和批判。

  审查清单：
  1. 逻辑漏洞：推理链是否完整？是否有跳跃或循环论证？
  2. 数据一致性：数据引用是否准确？不同段落的数据是否矛盾？
  3. 引用错误：引用的论文是否存在？引用内容是否准确反映原文？
  4. 方法论缺陷：实验设计是否有偏差？Baseline 选择是否公平？
  5. 遗漏与盲点：是否忽略了重要的相关工作或替代方法？
  6. 过度声明：结论是否超出了数据支持的范围？

  要求：
  - 严苛但有建设性
  - 每个质疑必须指出具体位置和原因
  - 提供改进建议
  - 按严重程度分级：critical / major / minor

user_template: |
  ## 审查目标
  产出阶段：{target_workflow}

  ## 待审查内容
  {content_to_review}
```

#### 裁决者

```yaml
name: critique/judge
version: "1.0.0"
description: "综合蓝方和红方意见，做出通过/打回裁决"

system: |
  你是审稿委员会主席，负责综合支持者和批评者的意见做出最终裁决。

  裁决标准：
  - 存在任何 critical 级别问题 → verdict=revise
  - major 问题 ≥ 2 个 → verdict=revise
  - 仅有 minor 问题 → verdict=pass，附带改进建议

  输出要求：
  - verdict: "pass" 或 "revise"
  - feedbacks: 结构化的修改意见列表（即使 pass 也可以有 minor 建议）
  - 每条 feedback 包含 category、severity、description、suggestion

user_template: |
  ## 支持者意见
  {supporter_opinion}

  ## 批评者意见
  {critic_opinion}

  ## 原始内容摘要
  产出阶段：{target_workflow}
```

**GEPA 评估指标**：Critique 的准确率（用人工标注的「好/坏产出物」验证裁决准确性）。

### 4.4 Ideation — Gap 分析（三步 Chain-of-Thought）

**设计决策**：拆成 3 步 CoT，每步输出喂给下一步，逐步从「归纳」到「发现」到「评估」。

这要求 Ideation WF 的 `analyze_gaps` 节点拆成 3 个子节点：

```
原: START → analyze_gaps → generate_designs → ...
新: START → gap_summarize → gap_compare → gap_evaluate → generate_designs → ...
```

#### 第 1 步：归纳总结

```yaml
name: ideation/gap_summarize
version: "1.0.0"
description: "CoT 第 1 步：从精读笔记中归纳各论文的核心方法和局限性"

system: |
  你是一位研究方法论专家。

  任务：阅读多篇论文的精读笔记，为每篇提取以下结构化摘要：
  1. 核心方法（一句话）
  2. 关键创新点
  3. 明确提到的局限性
  4. 隐含的局限性（从实验设计/数据范围推断）

  要求：
  - 忠实于原文，不添加未提及的信息
  - 局限性要具体，避免泛泛的「未来工作可以扩展」
  - 保留论文标识，便于后续交叉对比

user_template: |
  ## 精读笔记
  {reading_notes_json}
```

#### 第 2 步：交叉对比

```yaml
name: ideation/gap_compare
version: "1.0.0"
description: "CoT 第 2 步：交叉对比各论文方法，识别初步 Gap 候选"

system: |
  你是一位研究趋势分析专家。

  任务：基于上一步的归纳摘要，进行交叉对比分析：
  1. 方法维度对比：哪些问题被多篇论文从不同角度解决？各自优劣？
  2. 覆盖盲区识别：哪些重要方面没有被任何论文充分覆盖？
  3. 假设冲突检测：不同论文的基础假设是否存在矛盾？
  4. 组合创新机会：是否可以将论文 A 的方法应用于论文 B 的问题域？

  输出：初步 Gap 候选列表（不少于 3 个，每个含简要描述和来源论文）。

user_template: |
  ## 各论文归纳摘要（来自上一步）
  {gap_summaries_json}
```

#### 第 3 步：深化评估

```yaml
name: ideation/gap_evaluate
version: "1.0.0"
description: "CoT 第 3 步：对每个 Gap 候选评估学术价值和可行性"

system: |
  你是一位 {discipline} 领域的资深研究员。

  任务：对每个 Research Gap 候选进行深度评估：

  评估维度：
  1. 学术影响力（potential_impact）：填补此 Gap 能产生多大贡献？
  2. 证据支撑（supporting_evidence）：有哪些具体证据表明此 Gap 存在？
  3. 技术可行性：以当前技术水平，此 Gap 是否可被有效探索？
  4. 新颖性：是否已有其他未收录的工作在探索此 Gap？

  输出：按推荐优先级排序的 ResearchGap 列表。

user_template: |
  ## Gap 候选列表（来自上一步）
  {gap_candidates_json}

  ## 原始精读笔记（用于交叉验证）
  {reading_notes_json}
```

**GEPA 评估指标**：Gap 的学术价值打分（用领域专家标注的已知 Research Gap 作为 ground truth）。

### 4.5 其他节点 Prompt 概要

| 节点                        | Prompt 文件              | 核心设计要点                                    |
| --------------------------- | ------------------------ | ----------------------------------------------- |
| `extraction/generate_notes` | `generate_notes.yaml`    | 输入 RAG 召回段落，输出 `ReadingNote` 结构      |
| `extraction/cross_compare`  | `cross_compare.yaml`     | 输入多篇笔记，输出 `ComparisonEntry` 对比矩阵   |
| `extraction/build_glossary` | `build_glossary.yaml`    | 从笔记中提取专业术语，输出 `{term: definition}` |
| `ideation/generate_designs` | `generate_designs.yaml`  | 输入选定 Gap，输出 `ExperimentDesign` 方案      |
| `execution/generate_code`   | `generate_code.yaml`     | 输入任务描述，输出可执行 Python 代码            |
| `execution/reflect`         | `reflect.yaml`           | 输入错误日志，输出反思分析和修复方向            |
| `publish/assemble_outline`  | `assemble_outline.yaml`  | 从 artifacts 组装报告大纲                       |
| `publish/generate_markdown` | `generate_markdown.yaml` | 按大纲生成完整 Markdown 报告                    |

---

## 五、GEPA 集成架构（MVP 后独立分支）

### 5.1 设计决策

采用 **分层混合优化** 策略：

```
阶段 1: 按节点独立优化（每个 Prompt 有专属 evaluator）
         ↓ 各节点达到基线质量
阶段 2: 端到端微调（评估整条 Pipeline 最终输出质量）
```

### 5.2 集成架构

```
┌─────────────────────────────────────────────────────┐
│                GEPA Optimization Runner               │
│                                                       │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────┐ │
│  │ Seed Prompt │───►│ GEPA Engine  │───►│ Optimized│ │
│  │ (from YAML) │    │ (反射式进化)  │    │  Prompt  │ │
│  └─────────────┘    └──────┬───────┘    └────┬─────┘ │
│                            │                  │       │
│                     ┌──────▼───────┐    ┌────▼─────┐ │
│                     │  Evaluator   │    │ DB Write │ │
│                     │ (节点/端到端) │    │ (覆盖层) │ │
│                     └──────────────┘    └──────────┘ │
└─────────────────────────────────────────────────────┘
         │                                     │
         │ 读取 seed                           │ 写入优化结果
         ▼                                     ▼
    YAML 文件                          prompt_overrides 表
    (baseline)                         (source='gepa', active=true)
```

### 5.3 节点级 Evaluator 设计

每个可优化节点需要配套一个 evaluator，用于 GEPA 打分：

| 节点                             | Evaluator 策略                     | 评估数据来源                     |
| -------------------------------- | ---------------------------------- | -------------------------------- |
| `expand_query`                   | 扩展查询的检索召回率               | 历史 (query, relevant_papers) 对 |
| `supporter` / `critic` / `judge` | 裁决准确率（pass/revise 是否正确） | 人工标注的好/坏产出物            |
| `gap_summarize/compare/evaluate` | Gap 学术价值打分                   | 领域专家标注的已知 Gap           |
| `generate_code`                  | 代码执行成功率 + 输出正确性        | 历史代码任务及预期结果           |
| `generate_notes`                 | 笔记覆盖率 + 准确性                | 人工精读标注对照                 |

### 5.4 GEPA Adapter 实现

```python
from gepa.core.adapter import GEPAAdapter


class ResearchCopilotAdapter(GEPAAdapter):
    """Research Copilot 的 GEPA 适配器。

    将 Prompt 优化与项目的 YAML + DB 存储层对接。
    """

    def __init__(
        self,
        prompt_name: str,
        evaluator_fn: Callable[[str, list[dict]], float],
        db_session: AsyncSession,
    ) -> None:
        self._prompt_name = prompt_name
        self._evaluator_fn = evaluator_fn
        self._db = db_session

    def evaluate(self, candidate: str, dataset: list[dict]) -> float:
        """评估候选 Prompt 在数据集上的表现。"""
        return self._evaluator_fn(candidate, dataset)

    def make_reflective_dataset(self, dataset: list[dict]) -> list[dict]:
        """构造带反思信息的数据集（ASI — Actionable Side Information）。"""
        reflective = []
        for item in dataset:
            result = run_node_with_prompt(self._prompt_name, candidate_prompt, item)
            reflective.append({
                **item,
                "output": result.output,
                "error": result.error,
                "score": result.score,
            })
        return reflective

    async def save_optimized(self, optimized_prompt: str, score: float) -> None:
        """将优化结果写入 DB 覆盖层。"""
        # 先将同 name 的旧 active 记录关闭
        await self._db.execute(
            update(PromptOverride)
            .where(PromptOverride.name == self._prompt_name, PromptOverride.active == True)
            .values(active=False)
        )
        # 写入新版本
        new_override = PromptOverride(
            name=self._prompt_name,
            version=f"gepa-{datetime.now().strftime('%Y%m%d-%H%M')}",
            content={"system": optimized_prompt},
            source="gepa",
            score=score,
            active=True,
        )
        self._db.add(new_override)
        await self._db.commit()
```

### 5.5 优化执行流程

```python
import gepa

# 阶段 1: 节点独立优化
for prompt_name, evaluator_fn, dataset in NODE_OPTIMIZATION_TASKS:
    seed_prompt = load_yaml_prompt(prompt_name)

    result = gepa.optimize(
        seed_candidate={"system_prompt": seed_prompt.system},
        trainset=dataset["train"],
        valset=dataset["val"],
        task_lm="openai/gpt-4.1-mini",     # 被优化的执行模型
        reflection_lm="openai/gpt-5",       # 反思模型（更强）
        max_metric_calls=200,
    )

    adapter = ResearchCopilotAdapter(prompt_name, evaluator_fn, db_session)
    await adapter.save_optimized(result.best_candidate["system_prompt"], result.best_score)


# 阶段 2: 端到端微调（所有节点已有基线后）
# 固定其他节点 Prompt，逐个微调关键节点在端到端场景下的表现
for prompt_name in CRITICAL_NODES:
    e2e_result = gepa.optimize(
        seed_candidate={"system_prompt": load_current_best(prompt_name)},
        trainset=e2e_dataset["train"],
        valset=e2e_dataset["val"],
        task_lm="openai/gpt-4.1-mini",
        reflection_lm="openai/gpt-5",
        max_metric_calls=100,
    )
    await save_if_improved(prompt_name, e2e_result)
```

### 5.6 GEPA 优化优先级

按投入产出比排序，推荐的优化顺序：

| 优先级 | 节点                                            | 理由                                 |
| ------ | ----------------------------------------------- | ------------------------------------ |
| P0     | `critique/critic` + `critique/judge`            | 质量门禁，直接影响最终产出物质量     |
| P0     | `ideation/gap_evaluate`                         | 最依赖 LLM 推理能力，优化空间最大    |
| P1     | `supervisor/skeleton`                           | 路由准确率影响整条 Pipeline          |
| P1     | `execution/generate_code` + `execution/reflect` | 代码质量可量化评估                   |
| P2     | `discovery/expand_query`                        | 召回率可量化，但影响面相对较小       |
| P2     | `publish/generate_markdown`                     | 报告质量主观性强，评估函数设计难度高 |

---

## 六、Prompt 编写规范与反模式

### 6.1 编写规范

#### 命名约定

| 规则                                | 示例                                      |
| ----------------------------------- | ----------------------------------------- |
| 文件名 = 节点函数名                 | `expand_query` 节点 → `expand_query.yaml` |
| name 字段 = `wf/node`               | `discovery/expand_query`                  |
| 学科 snippet 文件名 = discipline 值 | `computer_science.yaml`                   |

#### 结构规范

1. **角色先行**：system prompt 第一行明确角色身份
2. **任务清晰**：紧跟角色后，用一句话描述当前任务
3. **维度枚举**：复杂任务用编号列表列出评估/操作维度
4. **约束在后**：要求和限制放在最后，用「要求：」标题引导
5. **不硬编码学科**：用 `{discipline}` 占位符，不写死 "计算机科学"

#### 占位符规范

```
{discipline}            — State 注入，PromptLoader 处理
{discipline_snippet}    — 学科 snippet 全文，仅 Supervisor
{available_skills}      — SkillRegistry 生成，仅 Supervisor
{topic}, {code}, ...    — 节点函数调用 render() 时传入
```

**规则**：占位符名全小写 + 下划线，与 Python 变量命名一致。system 中的占位符由 PromptLoader 管理（如 discipline_snippet），user_template 中的由节点函数管理。

### 6.2 反模式清单

| 反模式               | 问题                                               | 正确做法                                                |
| -------------------- | -------------------------------------------------- | ------------------------------------------------------- |
| **巨型 Prompt**      | 一个 Prompt 包办多个步骤（如 Gap 分析 + 方案生成） | 拆成独立节点，每个有自己的 Prompt                       |
| **学科硬编码**       | `你是计算机科学领域的专家` 写死在 Prompt 中        | 用 `{discipline}` 占位符                                |
| **输出格式口头约定** | "请以 JSON 格式输出" 但不用 structured_output      | 用 `with_structured_output(Pydantic Model)` 强制 schema |
| **上下文溢出**       | 把全部精读笔记塞进单个 Prompt                      | 按需召回（RAG），或拆 CoT 逐步消化                      |
| **指令歧义**         | "分析一下这些论文"                                 | 明确指定分析维度、输出结构、评估标准                    |
| **角色混淆**         | Critic prompt 里写 "也要指出优点"                  | 单一角色单一职责，优点由 Supporter 负责                 |
| **版本失控**         | 直接改 YAML 不改 version 字段                      | 任何修改必须递增 version                                |

### 6.3 Prompt 变更流程

```
1. 修改 YAML 文件 → 递增 version 字段
2. 本地测试（用目标节点的单元测试验证输出格式）
3. Code Review（Prompt 改动视同代码改动）
4. 合并后自动部署（YAML 随代码发布）
5. 如需紧急覆盖 → 写 DB override（source='manual'）
6. GEPA 优化结果 → 自动写 DB override（source='gepa'）
```

---

## 七、架构修订说明

本规范对前期设计文档产生以下修订：

### 7.1 LangGraph Agent 详细设计修订

**Ideation WF 节点拆分**：

原设计（`2026-03-19-langgraph-agent-design.md` 3.3 节）：
```
START → analyze_gaps → generate_designs → select_design → write_artifacts → END
```

修订为：
```
START → gap_summarize → gap_compare → gap_evaluate → generate_designs → select_design → write_artifacts → END
```

原 `analyze_gaps` 单节点拆成 3 个 CoT 子节点，每个对应独立的 Prompt 文件。`IdeationState` 需增加中间字段：

```python
class IdeationState(SharedState):
    """实验推演：识别 Research Gap，设计实验方案和评估体系。"""

    # CoT 中间产物（新增）
    gap_summaries: list[dict]
    """CoT 第 1 步产物：各论文归纳摘要。"""

    gap_candidates: list[dict]
    """CoT 第 2 步产物：初步 Gap 候选列表。"""

    # 原有字段不变
    research_gaps: list[ResearchGap]
    experiment_designs: list[ExperimentDesign]
    selected_design_index: int | None
```

### 7.2 ARCHITECT.md 修订

文件组织部分，`backend/agent/prompts/` 的描述从 `(.ymal)` 修正为完整目录结构（见本文第 1.2 节）。

### 7.3 DB Schema 新增

`prompt_overrides` 表需加入 PostgreSQL migration（在 FastAPI BFF 设计的 DB migration 流程中统一管理）。

---

## 八、设计决策索引

| #   | 决策项                 | 选择                                                        | 章节 |
| --- | ---------------------- | ----------------------------------------------------------- | ---- |
| 1   | Prompt 存储策略        | YAML baseline + DB 覆盖层                                   | 1.1  |
| 2   | YAML 模板格式          | 5 字段（name, version, description, system, user_template） | 1.3  |
| 3   | Supervisor prompt 结构 | 骨架 + 学科 snippet 注入                                    | 3.1  |
| 4   | 学科差异化             | snippet 独立文件，新增学科只需添加一个 YAML                 | 3.4  |
| 5   | Critique 对抗模式      | 蓝方/红方/裁决者三方独立 LLM 调用                           | 4.3  |
| 6   | Ideation Gap 分析      | 3 步 CoT（归纳→对比→评估）                                  | 4.4  |
| 7   | Prompt 加载优先级      | DB 覆盖 > YAML baseline                                     | 2.1  |
| 8   | GEPA 集成时机          | MVP 后独立分支                                              | 5.1  |
| 9   | GEPA 优化粒度          | 分层混合（节点独立 → 端到端微调）                           | 5.1  |
| 10  | GEPA 优化结果存储      | DB 覆盖层（source='gepa'）                                  | 5.4  |
