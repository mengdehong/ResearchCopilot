# 学术演示文稿生成 Skill 设计

> 将结构化科研产出自动转为专业学术演示文稿（PDF），支持 Typst 和 LaTeX Beamer 双渲染后端。

---

## 一、设计目标

- **内容提炼为核心**：LLM 从论文精读产出中提炼关键观点，按学术逻辑组织演示大纲
- **学术元素原生支持**：公式可编辑渲染、文献引用自动聚合、表格数据结构化展示
- **模板控制排版**：LLM 不接触排版代码，视觉质量由预制模板 100% 保证
- **双后端预留**：Typst（主推）和 LaTeX Beamer 共享同一 Slide Schema，按效果选用

---

## 二、技术决策记录

| 决策项     | 选择                                | 排除方案             | 理由                                               |
| ---------- | ----------------------------------- | -------------------- | -------------------------------------------------- |
| 输出格式   | PDF（Typst/Beamer 编译）            | PPTX（python-pptx）  | PPTX 不支持原生 LaTeX 公式、无代码高亮、无引用管理 |
| 渲染引擎   | Typst（主推）+ LaTeX Beamer（预留） | Marp                 | Typst 编译快、语法 LLM 友好；Beamer 模板生态成熟   |
| 架构模式   | LLM → Slide Schema JSON → 模板渲染  | LLM 直接生成渲染代码 | 关注点分离，LLM 专注内容，模板专注排版             |
| 公式语法   | Schema 中统一 LaTeX 语法            | Typst 原生语法       | LLM 对 LaTeX 数学最熟悉，Typst 侧自动转换          |
| Skill 模式 | subgraph                            | tool                 | 多步状态推进 + HITL 确认大纲                       |
| 编译环境   | Docker 沙盒内执行                   | 宿主机直接编译       | 安全隔离，与现有沙盒基建复用                       |

---

## 三、整体架构

### 数据流

```
上游 Workflow 产出物                    Skill 内部                              输出
(Extraction/Ideation/Execution)
                                   ┌─────────────────────────────────────┐
 精读笔记 ──────┐                  │    ppt_generation Skill (subgraph)  │
 对比矩阵 ──────┤                  │                                     │
 术语表   ──────┼──────────────────►│  ① plan_outline (LLM)              │
 实验图表 ──────┤                  │     产出大纲级 Slide Schema         │
 Gap 分析 ──────┘                  │         ↓                           │
                                   │  ② interrupt（HITL 确认大纲）       │
              用户选择              │         ↓                           │
 场景:论文汇报 ─────────────────────►│  ③ fill_content (LLM)              │  ┌─── .typ/.tex 源文件
 模板:学术蓝  ──────────────────────►│     逐页填充详细内容               ├──┤    (可编辑)
 后端:typst   ──────────────────────►│         ↓                           │  └─── .pdf 演示文稿
                                   │  ④ render（模板渲染 + 编译）        │
                                   └─────────────────────────────────────┘
```

### 三层解耦

| 层            | 职责                               | 负责方               |
| ------------- | ---------------------------------- | -------------------- |
| **内容层**    | 提炼演示内容、组织大纲、逐页分配   | LLM（Publish WF 中） |
| **Schema 层** | 结构化中间表示，描述每页版式与内容 | SlideSchema 模型     |
| **渲染层**    | Schema 填入模板源代码，编译为 PDF  | 模板引擎             |

---

## 四、Slide Schema 数据模型

### 顶层结构

```python
class PresentationSchema(BaseModel):
    """完整演示文稿的结构化描述"""
    meta: PresentationMeta
    slides: list[SlideSchema]

class PresentationMeta(BaseModel):
    scene: Literal["paper_presentation", "literature_review"]
    title: str
    subtitle: str | None = None
    authors: list[str]
    presenter: str | None = None
    date: str | None = None
    language: str = "zh"
    template_version: str | None = None
    references: list[Reference] = []

class Reference(BaseModel):
    key: str           # 引用 key，如 "vaswani2017"
    text: str          # 完整引用文本
```

### SlideSchema

```python
class SlideSchema(BaseModel):
    id: str                         # 唯一标识，方便定位调试
    layout: Literal[
        "title", "outline", "bullets", "formula",
        "figure", "table", "two_column", "summary", "references"
    ]
    section: str | None = None      # 所属章节
    notes: str | None = None        # 演讲者备注
    citations: list[str] = []       # 页级引用 key 列表
    content: SlideContent           # 联合类型，按 layout 变化
```

### 9 种版式 Content 定义

```python
# 1. 标题页 — 从 Meta 自动填充
class TitleContent(BaseModel):
    pass

# 2. 目录页 — 从 slides[].section 自动生成
class OutlineContent(BaseModel):
    active_index: int | None = None

# 3. 要点页
class BulletsContent(BaseModel):
    heading: str
    points: list[str]               # 支持 LaTeX 内联公式
    note: str | None = None

# 4. 公式页
class FormulaContent(BaseModel):
    heading: str
    formula: str                    # LaTeX 公式（居中突出）
    explanation: list[str]          # 变量/符号说明

# 5. 图文页
class FigureContent(BaseModel):
    heading: str
    image_ref: str                  # 图片资产路径
    caption: str
    points: list[str]
    layout: Literal["left_img", "right_img"] = "left_img"

# 6. 表格对比页
class TableContent(BaseModel):
    heading: str
    headers: list[str]
    rows: list[list[str]]
    highlight_best: bool = True

# 7. 双栏对比页
class TwoColumnContent(BaseModel):
    heading: str
    left_title: str
    left_points: list[str]
    right_title: str
    right_points: list[str]
    left_sentiment: Literal["positive", "neutral"] = "neutral"
    right_sentiment: Literal["negative", "neutral"] = "neutral"

# 8. 总结页
class SummaryContent(BaseModel):
    heading: str
    takeaways: list[str]

# 9. 参考文献页 — 从 Meta.references 自动生成
class ReferencesContent(BaseModel):
    pass
```

### 自动生成规则

| 页面类型   | 生成方式                                               |
| ---------- | ------------------------------------------------------ |
| 标题页     | 从 `PresentationMeta` 字段自动填充                     |
| 目录页     | 从所有 slide 的 `section` 字段收集，每个章节首页前插入 |
| 参考文献页 | 从 `Meta.references` + 所有 slide 的 `citations` 聚合  |

LLM 只需生成内容页（bullets、formula、figure、table、two_column、summary）。

---

## 五、渲染引擎

### 统一接口

```python
class SlideRenderer(Protocol):
    """渲染后端统一协议"""

    def render(
        self,
        schema: PresentationSchema,
        template_dir: Path,
        output_dir: Path,
    ) -> RenderedPresentation: ...

class RenderedPresentation(BaseModel):
    source_path: Path       # .typ 或 .tex 源文件
    pdf_path: Path          # 编译后的 PDF
    source_type: Literal["typst", "latex"]
    slide_count: int
```

### 渲染流程

```
 PresentationSchema
        │
        ▼
 RendererFactory.create(backend="typst"|"beamer")
        │
        ▼
 自动生成页面注入
   ├─ 标题页（从 Meta）
   ├─ 目录页（从 sections，每章节前插入）
   └─ 参考文献页（从 references + citations 聚合）
        │
        ▼
 逐页渲染：SlideSchema → 版式模板函数 → 源代码片段
        │
        ▼
 组装完整源文件（前导区 + 逐页内容 + 参考文献）
        │
        ▼
 编译：typst compile / latexmk → PDF（沙盒内执行）
        │
        ▼
 输出 RenderedPresentation
```

### 模板目录结构

```
backend/agent/skills/ppt_generation/
├── skill.yaml
├── execute.py                    # Skill 入口，构建 subgraph
├── schema.py                     # SlideSchema 全部数据模型
├── renderer/
│   ├── factory.py                # RendererFactory
│   ├── base.py                   # SlideRenderer Protocol
│   ├── auto_slides.py            # 自动页面生成（标题/目录/参考文献）
│   ├── typst_renderer.py         # Typst 渲染后端
│   └── beamer_renderer.py        # Beamer 渲染后端
│
└── templates/
    ├── typst/
    │   ├── academic_blue/        # 学术蓝主题
    │   │   ├── theme.typ         # 配色、字体、页面尺寸
    │   │   └── layouts.typ       # 9 种版式的 Typst 实现
    │   ├── minimal_dark/         # 深色简约主题
    │   │   ├── theme.typ
    │   │   └── layouts.typ
    │   └── shared/
    │       └── math_compat.typ   # LaTeX → Typst 公式转换
    │
    └── beamer/
        ├── academic_blue/
        │   ├── beamertheme.sty
        │   └── layouts.tex
        └── minimal_dark/
            ├── beamertheme.sty
            └── layouts.tex
```

### 关键设计决策

| 决策         | 选择                                 | 理由                                    |
| ------------ | ------------------------------------ | --------------------------------------- |
| 模板管理     | 静态文件，Skill 目录内               | YAGNI，不需要动态模板市场               |
| 公式转换     | LaTeX → Typst 自动转换               | LLM 对 LaTeX 最熟，Typst 侧工具函数处理 |
| 图片处理     | 渲染前拷贝到工作目录                 | 避免绝对路径问题                        |
| 编译环境     | Docker 沙盒                          | 安全隔离，镜像预装 typst + texlive      |
| 首批模板数量 | 2 套（academic_blue + minimal_dark） | 覆盖主流审美偏好                        |

---

## 六、Subgraph 节点设计

### 节点流程

```
plan_outline → interrupt("confirm_outline") → fill_content → render
```

### 各节点职责

| 节点           | 输入                          | 输出                            | 说明                          |
| -------------- | ----------------------------- | ------------------------------- | ----------------------------- |
| `plan_outline` | 上游产出物 + scene + template | 大纲级 Schema（content 仅标题） | LLM 决定分页、版式、章节划分  |
| `interrupt`    | 大纲 Schema                   | 用户确认/修改后的 Schema        | HITL 控制点，前端渲染大纲预览 |
| `fill_content` | 确认后的大纲 Schema           | 完整 Schema                     | LLM 逐页填充详细内容          |
| `render`       | 完整 Schema + template_dir    | RenderedPresentation            | 纯计算，不调 LLM              |

### SubgraphState

```python
class PPTGenerationState(TypedDict):
    content_sections: dict          # 上游产出物
    scene: str                      # 演示场景
    template_name: str              # 模板名称
    backend: str                    # 渲染后端
    outline_schema: PresentationSchema | None   # 大纲（plan_outline 产出）
    full_schema: PresentationSchema | None      # 完整内容（fill_content 产出）
    rendered: RenderedPresentation | None        # 渲染结果
```

---

## 七、Skill 接口

### skill.yaml

```yaml
name: ppt_generation
description: "将结构化研究成果渲染为专业学术演示文稿（PDF），支持 Typst 和 LaTeX Beamer 双后端"
mode: subgraph

input_schema:
  content_sections:
    type: dict
    required: true
    description: "上游 Workflow 产出物（精读笔记、对比矩阵、术语表、图表路径等）"
  scene:
    type: str
    required: true
    description: "演示场景：paper_presentation | literature_review"
  template_name:
    type: str
    required: false
    default: "academic_blue"
  backend:
    type: str
    required: false
    default: "typst"
    description: "渲染后端：typst | beamer"

output_schema:
  pdf_path:
    type: str
    description: "生成的 PDF 文件路径"
  source_path:
    type: str
    description: "可编辑的源文件路径（.typ 或 .tex）"
  slide_count:
    type: int
    description: "总页数"

entrypoint: execute.build_graph
```

### Publish Workflow 集成

```python
# Publish Workflow graph.py
publish_graph.add_node("assemble_report", assemble_report_node)
publish_graph.add_node("gen_ppt", registry.get_subgraph("ppt_generation"))
publish_graph.add_node("package_zip", package_zip_node)

publish_graph.add_edge("assemble_report", "gen_ppt")
publish_graph.add_edge("gen_ppt", "package_zip")
```

---

## 八、支持的演示场景

### 论文汇报 (paper_presentation)

| 章节       | 典型版式组合                                  |
| ---------- | --------------------------------------------- |
| 研究背景   | bullets + figure                              |
| 相关工作   | bullets + table（方法对比）                   |
| 方法论     | formula + figure（架构图）+ bullets           |
| 实验结果   | table（性能对比）+ figure（图表）+ two_column |
| 总结与展望 | summary                                       |

### 综述报告 (literature_review)

| 章节       | 典型版式组合               |
| ---------- | -------------------------- |
| 研究脉络   | bullets + figure（时间线） |
| 方法对比   | table（矩阵）+ two_column  |
| Gap 分析   | bullets + two_column       |
| 研究切入点 | bullets + formula          |
| 总结       | summary                    |

---

## 九、沙盒镜像扩展

现有沙盒镜像需追加：

```dockerfile
# 在 sandbox Dockerfile 中追加
RUN curl -fsSL https://typst.community/typst-install/install.sh | sh
# Beamer 后端需要 texlive（按需安装，体积较大）
RUN apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended
```

---

## 十、与 ARCHITECT.md 的关系

本设计细化了 ARCHITECT.md 中 `6_publish/` Workflow 的 PPT 渲染环节：

- 原设计：`Marp/python-pptx 渲染 PPTX`
- 新设计：`Typst/LaTeX Beamer 渲染 PDF`（公式可编辑、学术元素原生支持）
- 需同步更新 ARCHITECT.md 中 Publish WF 的描述

本 Skill 位于 `backend/agent/skills/ppt_generation/`，遵循 Skill 系统设计规范。
