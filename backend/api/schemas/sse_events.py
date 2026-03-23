"""SSE 事件 Payload 类型定义 — 对齐 SSE Event Protocol Design spec。

NOTE: 本模块当前仅被 event_broadcaster.py（EventBroadcaster）引用，
EventBroadcaster 本身尚未挂载到任何路由（文档解析进度推送功能待接入）。
保留此文件作为 Workspace 级 SSE 广播的类型合约，待 /workspace/events SSE
端点实现时激活。请勿删除。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

# ── 统一信封 ──


class SSEEvent(BaseModel):
    """SSE 事件统一信封。"""

    seq: int
    event_type: str
    timestamp: str
    payload: dict[str, Any]


# ── Run 通道 Payload ──


class RunStartPayload(BaseModel):
    """Run 开始。"""

    run_id: str
    thread_id: str
    workflow: str | None = None


class RunEndPayload(BaseModel):
    """Run 正常结束。"""

    run_id: str
    duration_ms: int


class RunErrorPayload(BaseModel):
    """Run 异常终止。"""

    run_id: str
    error_type: str
    message: str
    duration_ms: int


class NodeEnterPayload(BaseModel):
    """节点开始执行。"""

    node_id: str
    node_name: str
    parent_node_id: str | None = None


class NodeExitPayload(BaseModel):
    """节点执行完毕。"""

    node_id: str
    node_name: str
    status: Literal["completed", "failed", "skipped"]
    duration_ms: int


class TokenDeltaPayload(BaseModel):
    """LLM 流式增量 token。"""

    node_name: str
    delta: str
    role: Literal["assistant", "tool"]


class ContentGeneratedPayload(BaseModel):
    """Agent 产出结构化内容。"""

    content_type: Literal["markdown", "reading_note", "comparison_matrix", "glossary"]
    content: str
    target_tab: Literal["editor"] = "editor"


class ExecutionResultPayload(BaseModel):
    """沙盒代码执行结果。"""

    code: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    artifacts: list[str]
    target_tab: Literal["sandbox"] = "sandbox"


class PdfHighlightPayload(BaseModel):
    """RAG 溯源高亮定位。"""

    document_id: str
    page: int
    bbox: list[float]
    text_snippet: str
    target_tab: Literal["pdf"] = "pdf"


class InterruptPayload(BaseModel):
    """HITL 人类在环拦截。"""

    interrupt_type: Literal[
        "confirm_execute", "select_papers", "confirm_outline", "confirm_finalize"
    ]
    title: str
    description: str
    data: dict[str, Any]


# ── Workspace 通道 Payload ──


class DocParseStartedPayload(BaseModel):
    """文档开始解析。"""

    document_id: str
    filename: str


class DocParseProgressPayload(BaseModel):
    """解析进度更新。"""

    document_id: str
    stage: Literal["downloading", "parsing", "classifying", "embedding"]
    progress_pct: int


class DocParseCompletedPayload(BaseModel):
    """解析完成。"""

    document_id: str
    paragraph_count: int
    figure_count: int
    table_count: int
    duration_ms: int


class DocParseFailedPayload(BaseModel):
    """解析失败。"""

    document_id: str
    error_message: str
    stage: str
