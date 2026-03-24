"""Supervisor 主图编排。连接硬规则路由、LLM 路由、检查点回评和 6 个 WF subgraph。"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.agent.dspy_modules import registry as dspy_registry
from backend.agent.prompts.loader import load_prompt
from backend.agent.routing import (
    RouteDecision,
    StepEvaluation,
    apply_hard_rules,
    route_after_eval,
    route_to_workflow,
)
from backend.agent.state import SupervisorState
from backend.agent.workflows.critique.graph import build_critique_graph
from backend.agent.workflows.discovery.graph import build_discovery_graph
from backend.agent.workflows.execution.graph import build_execution_graph
from backend.agent.workflows.extraction.graph import build_extraction_graph
from backend.agent.workflows.ideation.graph import build_ideation_graph
from backend.agent.workflows.publish.graph import build_publish_graph
from backend.core.logger import get_logger
from backend.services.rag_engine import RAGEngine

logger = get_logger(__name__)

WORKFLOW_NAMES = ["discovery", "extraction", "ideation", "execution", "critique", "publish"]

# 审查目标推断顺序：按 pipeline 倒序，取最近有产出的 WF
_CRITIQUE_TARGET_ORDER = ["execution", "ideation", "extraction", "discovery"]

# Critique 打回最大迭代次数（蓝图要求 max 2 轮）
MAX_CRITIQUE_ROUNDS = 2

# 单步最大重试次数（retry_same），超出则回 Supervisor 重规划
MAX_STEP_RETRIES = 2


def _infer_critique_target(state: dict) -> str:
    """推断 critique 应审查的目标 WF。取 artifacts 中最新的非空 WF 命名空间。"""
    artifacts = state.get("artifacts", {})
    for wf in _CRITIQUE_TARGET_ORDER:
        if artifacts.get(wf):
            return wf
    return "execution"  # 安全回退


def _build_supervisor_node(llm: BaseChatModel):
    """构建 Supervisor 主控节点闭包。"""

    def supervisor_node(state: dict) -> dict:
        """Supervisor 主控节点：硬规则 → LLM 路由 → 更新 State。"""
        messages = state.get("messages", [])

        # 1. 硬规则检查
        hard_target = apply_hard_rules(messages)
        if hard_target:
            logger.info(
                "routing_decision",
                target=hard_target,
                mode="hard_rule",
            )
            return {
                "routing_decision": hard_target,
                "plan": None,
                "current_step_index": 0,
            }

        # 2. LLM 结构化输出路由（DSPy 优先，回退到 YAML）
        discipline = state.get("discipline", "")
        user_message = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content or ""
                break

        artifacts_summary = json.dumps(
            {
                k: list(v.keys()) if isinstance(v, dict) else str(v)
                for k, v in state.get("artifacts", {}).items()
            },
            ensure_ascii=False,
        )

        dspy_module = dspy_registry.get("supervisor_routing")
        if dspy_module is not None:
            logger.info("routing_via_dspy", module="supervisor_routing")
            decision = dspy_module(
                discipline=discipline,
                chat_history=user_message,
                current_artifacts=artifacts_summary,
            )
        else:
            prompt = load_prompt(
                "supervisor",
                variables={
                    "discipline": discipline,
                    "user_message": user_message,
                    "artifacts_summary": artifacts_summary,
                },
            )

            decision = llm.with_structured_output(RouteDecision).invoke(
                [
                    SystemMessage(content=prompt["system"]),
                    HumanMessage(content=prompt["user"]),
                ]
            )

        logger.info(
            "routing_decision",
            target=decision.target_workflow if decision.mode == "single" else "plan",
            mode=decision.mode,
            reasoning=decision.reasoning,
        )

        if decision.mode == "chat":
            reply = decision.reply_text or "我是 Research Copilot，有什么可以帮您？"
            logger.info(
                "routing_decision",
                target="__chat__",
                mode="chat",
                reasoning=decision.reasoning,
            )
            return {
                "routing_decision": "__chat__",
                "plan": None,
                "current_step_index": 0,
                "messages": [AIMessage(content=reply)],
            }

        if decision.mode == "single":
            target = decision.target_workflow or "__end__"
            result: dict = {
                "routing_decision": target,
                "plan": None,
                "current_step_index": 0,
            }
            # Bug-1 fix: critique needs target_workflow
            if target == "critique":
                result["target_workflow"] = _infer_critique_target(state)
            return result

        # mode == "plan"
        plan = decision.plan
        if not plan or not plan.steps:
            return {"routing_decision": "__end__", "plan": None, "current_step_index": 0}

        first_wf = plan.steps[0].workflow
        result = {
            "routing_decision": first_wf,
            "plan": plan,
            "current_step_index": 0,
            "artifacts": {
                "supervisor": {
                    "research_direction": decision.reasoning,
                    "goal": plan.goal,
                },
            },
        }
        # Bug-1 fix: critique needs target_workflow
        if first_wf == "critique":
            result["target_workflow"] = _infer_critique_target(state)
        return result

    return supervisor_node


def _handle_critique_revise(
    critique_results: dict,
    max_rounds: int,
) -> dict | None:
    """处理 Critique 打回逻辑。纯函数，返回 state update dict 或 None。"""
    for target_wf, result in critique_results.items():
        if not isinstance(result, dict) or result.get("verdict") != "revise":
            continue
        critique_round = result.get("round", 1)
        if critique_round >= max_rounds:
            logger.warning(
                "critique_max_rounds_reached",
                target=target_wf,
                round=critique_round,
                max_rounds=max_rounds,
            )
            continue
        feedbacks = result.get("feedbacks", [])
        feedback_text = "\n".join(
            f"- [{fb.get('severity', 'unknown')}] {fb.get('category', '')}: "
            f"{fb.get('description', '')} → {fb.get('suggestion', '')}"
            for fb in feedbacks
        )
        revision_message = HumanMessage(
            content=(
                f"根据模拟审稿意见，请修改 {target_wf} 阶段的产出物。"
                f"需要修正的问题：\n{feedback_text}\n"
                f"请基于以上反馈重新执行 {target_wf} 阶段。"
            )
        )
        return {
            "messages": [revision_message],
            "routing_decision": target_wf,
            "critique_round": critique_round + 1,
            "revision_context": feedback_text,
            "plan": None,
            "artifacts": {
                "critique": {
                    target_wf: {"verdict": "revision_in_progress"},
                },
            },
        }
    return None


def _build_checkpoint_eval_node(llm: BaseChatModel):
    """构建检查点回评节点闭包。"""

    def checkpoint_eval_node(state: dict) -> dict:
        """检查点回评：LLM 评估当前步骤 + Critique 打回处理。"""
        plan = state.get("plan")
        step_index = state.get("current_step_index", 0)

        # 特殊处理：Critique 打回
        critique_results = state.get("artifacts", {}).get("critique", {})
        revise_update = _handle_critique_revise(critique_results, MAX_CRITIQUE_ROUNDS)
        if revise_update is not None:
            logger.info(
                "checkpoint_eval",
                step_index=step_index,
                action="critique_revise",
                target=revise_update["routing_decision"],
                round=revise_update["critique_round"],
            )
            return revise_update

        # 无计划或已完成 → 结束
        if not plan:
            logger.info("checkpoint_eval", step_index=step_index, action="end_no_plan")
            return {"routing_decision": "__end__", "current_step_index": step_index + 1}

        # LLM 评估当前步骤
        current_step = plan.steps[step_index] if step_index < len(plan.steps) else None
        if not current_step:
            logger.info("checkpoint_eval", step_index=step_index, action="end_plan_complete")
            return {"routing_decision": "__end__", "current_step_index": step_index + 1}

        artifacts_summary = json.dumps(
            {
                k: list(v.keys()) if isinstance(v, dict) else str(v)
                for k, v in state.get("artifacts", {}).items()
            },
            ensure_ascii=False,
        )

        previous_steps = (
            [
                f"Step {i}: {plan.steps[i].workflow} - {plan.steps[i].objective}"
                for i in range(step_index)
            ]
            if step_index > 0
            else []
        )
        previous_steps_summary = "\n".join(previous_steps) if previous_steps else "无"

        prompt = load_prompt(
            "checkpoint_eval",
            variables={
                "objective": current_step.objective,
                "success_criteria": current_step.success_criteria,
                "artifacts_summary": artifacts_summary,
                "previous_steps_summary": previous_steps_summary,
            },
        )

        evaluation = llm.with_structured_output(StepEvaluation).invoke(
            [
                SystemMessage(content=prompt["system"]),
                HumanMessage(content=prompt["user"]),
            ]
        )

        if evaluation.passed:
            next_index = step_index + 1
            if next_index >= len(plan.steps):
                logger.info(
                    "checkpoint_eval",
                    step_index=step_index,
                    passed=True,
                    reason="plan complete",
                )
                return {"routing_decision": "__end__", "current_step_index": next_index}

            next_wf = plan.steps[next_index].workflow
            logger.info(
                "checkpoint_eval",
                step_index=step_index,
                passed=True,
                reason="advancing to next step",
                next_wf=next_wf,
            )
            result = {
                "routing_decision": next_wf,
                "current_step_index": next_index,
                "_step_retry_count": 0,
            }
            # Bug-1 fix: critique needs target_workflow from previous step
            if next_wf == "critique":
                result["target_workflow"] = plan.steps[step_index].workflow
            return result

        # retry_same → 重试当前步骤（含重试次数保护）
        step_retry_count = state.get("_step_retry_count", 0)
        if evaluation.retry_same and step_retry_count < MAX_STEP_RETRIES:
            current_wf = current_step.workflow
            logger.info(
                "checkpoint_eval",
                step_index=step_index,
                passed=False,
                action="retry_same",
                wf=current_wf,
                retry=step_retry_count + 1,
            )
            return {
                "routing_decision": current_wf,
                "current_step_index": step_index,
                "_step_retry_count": step_retry_count + 1,
            }

        # 不通过 + 不重试 → 回到 Supervisor 重新规划
        logger.info(
            "checkpoint_eval",
            step_index=step_index,
            passed=False,
            reason=evaluation.reason,
            suggestion=evaluation.suggestion,
        )
        return {"routing_decision": "__replan__", "plan": None, "_step_retry_count": 0}

    return checkpoint_eval_node


def build_supervisor_graph(
    *,
    llm: BaseChatModel,
    rag_engine: RAGEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> StateGraph:
    """构建 Supervisor 主图。

    Args:
        llm: LLM 实例，注入到 Supervisor 节点和所有 WF subgraph。
        rag_engine: RAG 检索引擎实例。
        session_factory: DB session 工厂，供 RAG 检索使用。
    """
    graph = StateGraph(SupervisorState)

    # 节点注册
    graph.add_node("supervisor", _build_supervisor_node(llm))
    graph.add_node("checkpoint_eval", _build_checkpoint_eval_node(llm))

    # 6 个 WF 作为 compiled subgraph 节点
    graph.add_node("discovery", build_discovery_graph(llm=llm).compile())
    graph.add_node(
        "extraction",
        build_extraction_graph(
            llm=llm, rag_engine=rag_engine, session_factory=session_factory
        ).compile(),
    )
    graph.add_node("ideation", build_ideation_graph(llm=llm).compile())
    graph.add_node("execution", build_execution_graph(llm=llm).compile())
    graph.add_node("critique", build_critique_graph(llm=llm).compile())
    graph.add_node("publish", build_publish_graph(llm=llm).compile())

    # 边连接
    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_to_workflow,
        {wf: wf for wf in WORKFLOW_NAMES} | {"__end__": END},
    )

    for wf in WORKFLOW_NAMES:
        graph.add_edge(wf, "checkpoint_eval")

    graph.add_conditional_edges(
        "checkpoint_eval",
        route_after_eval,
        {wf: wf for wf in WORKFLOW_NAMES} | {"supervisor": "supervisor", "__end__": END},
    )

    return graph
