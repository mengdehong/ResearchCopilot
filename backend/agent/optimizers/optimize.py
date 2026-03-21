"""DSPy Prompt 优化统一入口。

用法:
    uv run python -m backend.agent.optimizers.optimize supervisor           # 模板数据
    uv run python -m backend.agent.optimizers.optimize supervisor --adversarial  # LLM 对抗数据
    uv run python -m backend.agent.optimizers.optimize all --adversarial --total 200
"""

import argparse
import os

try:
    import dspy
except ImportError as exc:
    raise ImportError("dspy is required. Install with: uv sync --extra optimization") from exc

from backend.core.logger import get_logger

logger = get_logger(__name__)


def _init_dspy_lm() -> dspy.LM:
    """从环境变量初始化 DSPy LM。"""
    model = os.environ.get("DSPY_MODEL", "gemini/gemini-2.5-flash")
    logger.info("dspy_lm_init", model=model)

    lm = dspy.LM(model, temperature=0.0)
    dspy.configure(lm=lm)
    return lm


def _to_supervisor_examples(raw_dataset: list[dict]) -> list[dspy.Example]:
    """将原始数据转换为 DSPy Example 列表。"""
    from backend.agent.routing import RouteDecision

    examples: list[dspy.Example] = []
    skipped = 0
    for data in raw_dataset:
        try:
            routing_dict = data["routing_decision"]
            # 确保 routing_decision 合法
            routing_decision = RouteDecision(**routing_dict)
            example = dspy.Example(
                discipline=data["discipline"],
                chat_history=data["chat_history"],
                current_artifacts=data.get("current_artifacts", "[]"),
                routing_decision=routing_decision,
            ).with_inputs("discipline", "chat_history", "current_artifacts")
            examples.append(example)
        except Exception as e:
            skipped += 1
            logger.warning("supervisor_example_skipped", error=str(e)[:80])
    if skipped:
        logger.info("supervisor_examples_skipped", count=skipped)
    return examples


def _to_discovery_examples(raw_dataset: list[dict]) -> list[dspy.Example]:
    """将原始数据转换为 DSPy Example 列表。"""
    from backend.agent.dspy_modules.discovery import RelevanceCard

    examples: list[dspy.Example] = []
    skipped = 0
    for data in raw_dataset:
        try:
            is_selected = data["is_selected"]
            example = dspy.Example(
                discipline=data["discipline"],
                user_search_intent=data["user_search_intent"],
                paper_title=data["paper_title"],
                paper_abstract=data["paper_abstract"],
                is_selected=is_selected,
                evaluation=RelevanceCard(
                    relevance_score=1.0 if is_selected else 0.0,
                    relevance_comment="",
                ),
            ).with_inputs(
                "discipline",
                "user_search_intent",
                "paper_title",
                "paper_abstract",
            )
            examples.append(example)
        except Exception as e:
            skipped += 1
            logger.warning("discovery_example_skipped", error=str(e)[:80])
    if skipped:
        logger.info("discovery_examples_skipped", count=skipped)
    return examples


def run_supervisor_optimization(total: int, seed: int, adversarial: bool) -> None:
    """运行 Supervisor 路由 prompt 编译全流程。"""
    from backend.agent.dspy_modules.supervisor import SupervisorRouterModule
    from backend.agent.optimizers.run_supervisor import (
        compile_and_save,
        evaluate_baseline,
    )

    logger.info(
        "supervisor_optimization_start",
        total=total,
        seed=seed,
        adversarial=adversarial,
    )

    # 1. 生成数据
    if adversarial:
        from backend.agent.optimizers.datasets.supervisor_adversarial import (
            generate_full_dataset,
        )

        raw_dataset = generate_full_dataset(total=total, seed=seed)
    else:
        from backend.agent.optimizers.datasets.supervisor_gen import generate_dataset

        raw_dataset = generate_dataset(total=total, seed=seed)

    examples = _to_supervisor_examples(raw_dataset)
    if len(examples) < 10:
        logger.error("supervisor_insufficient_data", count=len(examples))
        return

    split = int(len(examples) * 0.8)
    trainset = examples[:split]
    valset = examples[split:]

    logger.info(
        "supervisor_dataset_ready",
        total=len(examples),
        train=len(trainset),
        val=len(valset),
    )

    # 2. Baseline 评估
    baseline_score = evaluate_baseline(SupervisorRouterModule(), valset)
    logger.info("supervisor_baseline", score=baseline_score)

    # 3. 编译
    optimized_score = compile_and_save(trainset, valset)
    logger.info(
        "supervisor_optimization_done",
        baseline=baseline_score,
        optimized=optimized_score,
        improvement=round(optimized_score - baseline_score, 2),
    )


def run_discovery_optimization(total: int, seed: int, adversarial: bool) -> None:
    """运行 Discovery 排序 prompt 编译全流程。"""
    from backend.agent.dspy_modules.discovery import FilterRankModule
    from backend.agent.optimizers.run_discovery import (
        compile_and_save,
        evaluate_baseline,
    )

    logger.info(
        "discovery_optimization_start",
        total=total,
        seed=seed,
        adversarial=adversarial,
    )

    # 1. 生成数据
    if adversarial:
        from backend.agent.optimizers.datasets.discovery_adversarial import (
            generate_full_dataset,
        )

        raw_dataset = generate_full_dataset(total=total, seed=seed)
    else:
        from backend.agent.optimizers.datasets.discovery_gen import (
            generate_discovery_dataset,
        )

        raw_dataset = generate_discovery_dataset(total=total, seed=seed)

    examples = _to_discovery_examples(raw_dataset)
    if len(examples) < 10:
        logger.error("discovery_insufficient_data", count=len(examples))
        return

    split = int(len(examples) * 0.8)
    trainset = examples[:split]
    valset = examples[split:]

    logger.info(
        "discovery_dataset_ready",
        total=len(examples),
        train=len(trainset),
        val=len(valset),
    )

    # 2. Baseline 评估
    baseline_score = evaluate_baseline(FilterRankModule(), valset)
    logger.info("discovery_baseline", score=baseline_score)

    # 3. 编译
    optimized_score = compile_and_save(trainset, valset)
    logger.info(
        "discovery_optimization_done",
        baseline=baseline_score,
        optimized=optimized_score,
        improvement=round(optimized_score - baseline_score, 2),
    )


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="DSPy Prompt 优化统一入口")
    parser.add_argument(
        "target",
        choices=["supervisor", "discovery", "all"],
        help="优化目标",
    )
    parser.add_argument("--total", type=int, default=200, help="样本数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument(
        "--adversarial",
        action="store_true",
        help="使用 LLM 生成对抗性数据 (需要 API 调用)",
    )
    args = parser.parse_args()

    _init_dspy_lm()

    if args.target in ("supervisor", "all"):
        run_supervisor_optimization(
            total=args.total,
            seed=args.seed,
            adversarial=args.adversarial,
        )

    if args.target in ("discovery", "all"):
        run_discovery_optimization(
            total=args.total,
            seed=args.seed,
            adversarial=args.adversarial,
        )

    logger.info("optimization_complete", target=args.target)


if __name__ == "__main__":
    main()
