"""Supervisor 路由 DSPy Module。将 LLM 路由决策抽象为可编译的 DSPy Signature + Module。"""

try:
    import dspy
except ImportError as exc:
    raise ImportError(
        "dspy is required for optimization modules. Install with: uv sync --extra optimization"
    ) from exc

from backend.agent.routing import RouteDecision


class SupervisorRoutingSignature(dspy.Signature):
    """作为研究助手的核心路由，分析用户的请求，决定将其派发给哪个具体的 Workflow，
    或者为其制定一个多步工作流计划。"""

    discipline: str = dspy.InputField(desc="用户的学科背景，如 'computer_science'")
    chat_history: str = dspy.InputField(desc="最近的对话上下文")
    current_artifacts: str = dspy.InputField(desc="当前已生成的研究产出物摘要")

    routing_decision: RouteDecision = dspy.OutputField(
        desc="包含 mode (single/plan/chat), target_workflow, plan, reasoning 的结构化输出"
    )


class SupervisorRouterModule(dspy.Module):
    """Supervisor 路由模块。使用 ChainOfThought 强制推理后输出路由决策。"""

    def __init__(self) -> None:
        super().__init__()
        self.prog = dspy.ChainOfThought(SupervisorRoutingSignature)

    def forward(
        self,
        discipline: str,
        chat_history: str,
        current_artifacts: str,
    ) -> RouteDecision:
        result = self.prog(
            discipline=discipline,
            chat_history=chat_history,
            current_artifacts=current_artifacts,
        )
        return result.routing_decision
