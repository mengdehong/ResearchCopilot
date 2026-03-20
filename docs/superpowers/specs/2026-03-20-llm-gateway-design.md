# LLM Gateway 设计

> LLM 统一调用层：双 Tier 模型池、同 Tier 横向 Fallback、Structured Output 封装。

---

## 一、设计决策记录

| 决策项            | 选择                               | 排除方案                            | 理由                                     |
| ----------------- | ---------------------------------- | ----------------------------------- | ---------------------------------------- |
| 模型路由          | 双 Tier 池（reasoning + fast）     | 固定 provider 优先级链              | 各节点对模型能力需求不同，分 tier 更精准 |
| Fallback          | 同 Tier 横向切换                   | 跨 Tier 降级                        | 保证质量不降级                           |
| 重试              | 指数退避，单 Provider 最多 3 次    | 无限重试                            | 快速 Fallback 比等待重试更高效           |
| Structured Output | Gateway 层统一 `invoke_structured` | 各节点自行 `with_structured_output` | 消除重复代码，统一错误处理               |
| Cost Tracking     | MVP 通过 `quota_records` 记录      | Gateway 层自动化                    | YAGNI，MVP 阶段手动记录足够              |
| BYOK              | MVP 不实现                         | 用户自带 Key 路由                   | MVP 阶段使用平台 Key                     |

---

## 二、模型 Tier 配置

### 2.1 Reasoning Tier（强推理）

用途：Supervisor 路由、Critique 裁决、Gap 分析、跨文档对比

| 优先级 | Provider  | 模型 ID             | 上下文窗口 | 
| ------ | --------- | ------------------- | ---------- | 
| 1      | OpenAI    | `gpt-5.4`           | 1M tokens  | 
| 2      | Anthropic | `claude-sonnet-4.6` | 1M tokens  | 
| 3      | Google    | `gemini-3.1-pro`    | 1M tokens  | 

### 2.2 Fast Tier（快速/低成本）

用途：查询扩展、代码生成、笔记生成、Markdown 渲染

| 优先级 | Provider  | 模型 ID                 | 特点                 |
| ------ | --------- | ----------------------- | -------------------- |
| 1      | OpenAI    | `gpt-5.4-mini`          | 速度是 GPT-5 mini 2x |
| 2      | Anthropic | `claude-haiku-4.5`      | 最快最经济           |
| 3      | Google    | `gemini-3.1-flash-lite` | Google 最快最便宜    |

### 2.3 节点 Tier 分配

| Workflow / 节点                | Tier      | 理由                 |
| ------------------------------ | --------- | -------------------- |
| Supervisor 路由决策            | reasoning | 需要理解复杂意图     |
| Discovery → `expand_query`     | fast      | 简单文本变换         |
| Extraction → `generate_notes`  | reasoning | 需要深度理解论文内容 |
| Extraction → `cross_compare`   | reasoning | 跨文档推理           |
| Extraction → `build_glossary`  | fast      | 简单提取             |
| Ideation → `gap_*`（三步 CoT） | reasoning | 核心推理链           |
| Ideation → `generate_designs`  | reasoning | 实验方案设计         |
| Execution → `generate_code`    | fast      | 代码生成             |
| Execution → `reflect`          | reasoning | 需要深度反思         |
| Critique → `supporter/critic`  | reasoning | 需要审稿级推理       |
| Critique → `judge`             | reasoning | 裁决质量直接影响产出 |
| Publish → `assemble_outline`   | fast      | 结构化组装           |
| Publish → `generate_markdown`  | fast      | 文本生成             |

---

## 三、Fallback 与重试机制

### 3.1 Fallback 流程

```
节点请求 LLM（tier=reasoning）
  → 尝试 Provider 1（gpt-5.4）
    → 成功 → 返回结果
    → 失败（超时/429/5xx/APIError）→ 指数退避重试（最多 3 次）
      → 全部重试失败 → 切换到 Provider 2（claude-sonnet-4.6）
        → 成功 → 返回结果（日志标记 fallback）
        → 全部重试失败 → 切换到 Provider 3（gemini-3.1-pro）
          → 成功 → 返回结果（日志标记 fallback）
          → 全部重试失败 → 抛出 LLMUnavailableError
```

### 3.2 重试参数

| 参数               | 值                               | 说明           |
| ------------------ | -------------------------------- | -------------- |
| 单 Provider 重试数 | 3                                | —              |
| 退避基数           | 1s                               | 1s → 2s → 4s   |
| 退避乘数           | 2                                | —              |
| 单次超时           | 60s                              | reasoning tier |
| 单次超时           | 30s                              | fast tier      |
| 可重试错误         | 429, 500, 502, 503, 504, Timeout | —              |

### 3.3 Fallback 日志

```python
logger.warning(
    "llm_provider_fallback",
    original_provider=original_provider,
    fallback_provider=fallback_provider,
    tier=tier,
    error_type=str(type(error).__name__),
    retry_count=retry_count,
)
```

---

## 四、API 设计

### 4.1 核心接口

```python
class ModelTier(StrEnum):
    """模型能力分级。"""
    REASONING = "reasoning"
    FAST = "fast"


class LLMGateway:
    """LLM 统一网关。双 Tier 模型池 + 同 Tier 横向 Fallback。"""

    def __init__(
        self,
        *,
        config: LLMConfig,
    ) -> None:
        """初始化模型池。

        Args:
            config: 包含各 Provider API Key 和 Tier 配置。
        """
        ...

    def get_model(
        self,
        *,
        tier: ModelTier = ModelTier.FAST,
        temperature: float = 0.0,
    ) -> BaseChatModel:
        """获取指定 Tier 的 LLM 实例（首选 Provider）。"""
        ...

    async def invoke(
        self,
        messages: list[BaseMessage],
        *,
        tier: ModelTier = ModelTier.FAST,
        temperature: float = 0.0,
    ) -> BaseMessage:
        """调用 LLM，带 Fallback + 重试 + 结构化日志。"""
        ...

    async def invoke_structured(
        self,
        messages: list[BaseMessage],
        output_schema: type[BaseModel],
        *,
        tier: ModelTier = ModelTier.FAST,
        temperature: float = 0.0,
    ) -> BaseModel:
        """调用 LLM 并解析为结构化输出。

        内部使用 with_structured_output()，统一处理解析失败重试。
        """
        ...
```

### 4.2 配置模型

```python
class ProviderConfig(BaseModel):
    """单个 Provider 配置。"""
    provider: LLMProvider
    model: str
    api_key: str
    timeout_seconds: int = 60

class TierConfig(BaseModel):
    """单个 Tier 的 Provider 优先级链。"""
    providers: list[ProviderConfig]     # 按优先级排序

class LLMConfig(BaseModel):
    """LLM Gateway 完整配置。"""
    tiers: dict[ModelTier, TierConfig]
    max_retries: int = 3
    retry_base_seconds: float = 1.0
    retry_multiplier: float = 2.0
```

### 4.3 配置示例

```python
llm_config = LLMConfig(
    tiers={
        ModelTier.REASONING: TierConfig(providers=[
            ProviderConfig(provider=LLMProvider.OPENAI, model="gpt-5.4", api_key="..."),
            ProviderConfig(provider=LLMProvider.ANTHROPIC, model="claude-sonnet-4.6", api_key="..."),
            ProviderConfig(provider=LLMProvider.GOOGLE, model="gemini-3.1-pro", api_key="..."),
        ]),
        ModelTier.FAST: TierConfig(providers=[
            ProviderConfig(provider=LLMProvider.OPENAI, model="gpt-5.4-mini", api_key="..."),
            ProviderConfig(provider=LLMProvider.ANTHROPIC, model="claude-haiku-4.5", api_key="..."),
            ProviderConfig(provider=LLMProvider.GOOGLE, model="gemini-3.1-flash-lite", api_key="..."),
        ]),
    },
)
```

---

## 五、Structured Output 封装

### 5.1 设计要点

`invoke_structured` 在 `invoke` 基础上增加：

1. **Schema 绑定**：自动调用 `model.with_structured_output(output_schema)`
2. **解析失败重试**：如果 LLM 返回的 JSON 无法解析为目标 schema，自动追加错误信息重试（最多 2 次）
3. **统一错误类型**：解析失败抛出 `StructuredOutputError`，携带原始响应

### 5.2 调用示例

```python
from backend.agent.workflows.discovery.state import SearchQueries

async def expand_query(state: DiscoveryState) -> dict:
    """Discovery WF：LLM 扩展查询词。"""
    prompt = await prompt_loader.load("discovery/expand_query")
    system_content, user_content = prompt.render(
        discipline=state["discipline"],
        topic=state["messages"][-1].content,
    )

    result = await llm_gateway.invoke_structured(
        messages=[
            SystemMessage(content=system_content),
            HumanMessage(content=user_content),
        ],
        output_schema=SearchQueries,
        tier=ModelTier.FAST,
    )

    return {"search_queries": result.queries}
```

---

## 六、与现有代码的关系

### 6.1 现有 `llm_gateway.py` 改造

现有 114 行实现需要以下增强：

| 改动                     | 说明                                               |
| ------------------------ | -------------------------------------------------- |
| 新增 `ModelTier`         | 替代原有的 `provider` + `model` 显式指定           |
| 重构 `__init__`          | 接收 `LLMConfig` 替代分散的 API Key 参数           |
| 新增 Fallback 循环       | `invoke` 方法内增加 Provider 链遍历 + 指数退避重试 |
| 新增 `invoke_structured` | 封装 `with_structured_output` + 解析失败重试       |
| 保留 `get_model`         | 兼容 LangGraph 节点直接使用 ChatModel 的场景       |

### 6.2 向后兼容

`get_model(provider=..., model=...)` 签名保留不变，新增 `tier` 参数作为推荐用法：

```python
# 旧用法（仍然有效）
model = gateway.get_model(provider=LLMProvider.OPENAI, model="gpt-5.4")

# 新用法（推荐）
model = gateway.get_model(tier=ModelTier.REASONING)
```

---

## 七、可观测性集成

每次 LLM 调用记录结构化日志：

| 字段            | 说明                        |
| --------------- | --------------------------- |
| `tier`          | 请求的 Tier                 |
| `provider`      | 实际使用的 Provider         |
| `model`         | 实际使用的模型 ID           |
| `input_tokens`  | 输入 token 数               |
| `output_tokens` | 输出 token 数               |
| `latency_ms`    | 调用耗时                    |
| `is_fallback`   | 是否经过 Fallback           |
| `retry_count`   | 重试次数                    |
| `is_structured` | 是否 structured output 调用 |

对齐 Observability Spec §2.4 中的 `llm_call_completed` 事件。
