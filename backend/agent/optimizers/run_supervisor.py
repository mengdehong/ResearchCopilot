"""Supervisor 路由 MIPROv2 编译脚本。

运行方式:
    uv run python -m backend.agent.optimizers.run_supervisor              # 完整编译
    uv run python -m backend.agent.optimizers.run_supervisor --eval-only  # 仅评估 baseline
"""

import argparse
import json
from pathlib import Path

try:
    import dspy
    from dspy.teleprompt import MIPROv2
except ImportError as exc:
    raise ImportError("dspy is required. Install with: uv sync --extra optimization") from exc

from backend.agent.dspy_modules.supervisor import SupervisorRouterModule
from backend.agent.optimizers.metrics.supervisor_metric import (
    supervisor_routing_metric,
)
from backend.agent.routing import RouteDecision
from backend.core.logger import get_logger

logger = get_logger(__name__)

COMPILED_OUTPUT = Path(__file__).parent.parent / "compiled_prompts" / "supervisor_routing.json"


def load_dataset(path: str) -> list[dspy.Example]:
    """从 JSONL 文件加载 DSPy Example 数据集。"""
    examples: list[dspy.Example] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line.strip())
            routing_dict = data["routing_decision"]
            routing_decision = RouteDecision(**routing_dict)
            example = dspy.Example(
                discipline=data["discipline"],
                chat_history=data["chat_history"],
                current_artifacts=data["current_artifacts"],
                routing_decision=routing_decision,
            ).with_inputs("discipline", "chat_history", "current_artifacts")
            examples.append(example)
    return examples


def evaluate_baseline(
    module: SupervisorRouterModule,
    dataset: list[dspy.Example],
) -> float:
    """评估 baseline（未编译）的准确率。"""
    evaluator = dspy.Evaluate(
        devset=dataset,
        metric=supervisor_routing_metric,
        num_threads=8,
        display_progress=True,
    )
    score = evaluator(module)
    # DSPy v3: Evaluate 返回 EvaluationResult 而非 float
    score_val = score.score if hasattr(score, "score") else float(score)
    logger.info("baseline_evaluation", score=score_val)
    return score_val


def compile_and_save(
    trainset: list[dspy.Example],
    valset: list[dspy.Example],
    output_path: Path = COMPILED_OUTPUT,
) -> float:
    """运行 MIPROv2 编译并保存产物。"""
    teleprompter = MIPROv2(
        metric=supervisor_routing_metric,
        auto="light",
        num_threads=8,
    )

    compiled_router = teleprompter.compile(
        SupervisorRouterModule(),
        trainset=trainset,
        valset=valset,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    compiled_router.save(str(output_path))
    logger.info("compiled_module_saved", path=str(output_path))

    # 编译后评估
    evaluator = dspy.Evaluate(
        devset=valset,
        metric=supervisor_routing_metric,
        num_threads=8,
        display_progress=True,
    )
    optimized_score = evaluator(compiled_router)
    score_val = (
        optimized_score.score if hasattr(optimized_score, "score") else float(optimized_score)
    )
    logger.info("optimized_evaluation", score=score_val)
    return score_val


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="Supervisor 路由 DSPy 编译")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/supervisor_train.jsonl",
        help="训练数据 JSONL 路径",
    )
    parser.add_argument("--eval-only", action="store_true", help="仅评估 baseline")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="训练集比例")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    split = int(len(dataset) * args.train_ratio)
    trainset = dataset[:split]
    valset = dataset[split:]

    logger.info(
        "dataset_loaded",
        total=len(dataset),
        train=len(trainset),
        val=len(valset),
    )

    if args.eval_only:
        evaluate_baseline(SupervisorRouterModule(), valset)
    else:
        compile_and_save(trainset, valset)


if __name__ == "__main__":
    main()
