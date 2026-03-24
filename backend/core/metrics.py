"""Prometheus 应用级指标定义。

模块加载时注册，全局单例，避免重复注册。
外部通过 `from backend.core.metrics import llm_tokens_total, llm_requests_total` 使用。
"""

from prometheus_client import Counter

# 使用默认注册表（与 prometheus_fastapi_instrumentator 共享同一 /metrics 端点）
# 若需要测试隔离，可在测试中 mock 这些对象。

llm_tokens_total: Counter = Counter(
    name="llm_tokens_total",
    documentation="LLM API 消耗的 token 总量",
    labelnames=["model", "workspace_id", "token_type"],
)
"""按 model / workspace_id / token_type(input|output) 分组的 token 计数。"""

llm_requests_total: Counter = Counter(
    name="llm_requests_total",
    documentation="LLM 调用次数（含 quota_exceeded 失败）",
    labelnames=["model", "workspace_id", "status"],
)
"""按 model / workspace_id / status(ok|quota_exceeded) 分组的请求计数。"""
