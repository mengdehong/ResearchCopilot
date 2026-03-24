"""Discovery 排序 BootstrapFewShot 编译脚本。

运行方式:
    uv run python -m backend.agent.optimizers.run_discovery              # 完整编译
    uv run python -m backend.agent.optimizers.run_discovery --eval-only  # 仅评估 baseline
"""

import argparse
import json
from pathlib import Path

try:
    import dspy
    from dspy.teleprompt import BootstrapFewShotWithRandomSearch
except ImportError as exc:
    raise ImportError("dspy is required. Install with: uv sync --extra optimization") from exc

from backend.agent.dspy_modules.discovery import FilterRankModule, RelevanceCard
from backend.agent.optimizers.metrics.discovery_metric import (
    discovery_relevance_metric,
)
from backend.core.logger import get_logger

logger = get_logger(__name__)

COMPILED_OUTPUT = Path(__file__).parent.parent / "compiled_prompts" / "filter_rank.json"


def load_dataset(path: str) -> list[dspy.Example]:
    """从 JSONL 文件加载 DSPy Example 数据集。"""
    examples: list[dspy.Example] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line.strip())
            example = dspy.Example(
                discipline=data["discipline"],
                user_search_intent=data["user_search_intent"],
                paper_title=data["paper_title"],
                paper_abstract=data["paper_abstract"],
                is_selected=data["is_selected"],
                evaluation=RelevanceCard(
                    relevance_score=1.0 if data["is_selected"] else 0.0,
                    relevance_comment="",
                ),
            ).with_inputs(
                "discipline",
                "user_search_intent",
                "paper_title",
                "paper_abstract",
            )
            examples.append(example)
    return examples


def evaluate_baseline(
    module: FilterRankModule,
    dataset: list[dspy.Example],
) -> float:
    """评估 baseline 的平均得分。"""
    evaluator = dspy.Evaluate(
        devset=dataset,
        metric=discovery_relevance_metric,
        num_threads=8,
        display_progress=True,
    )
    score = evaluator(module)
    score_val = score.score if hasattr(score, "score") else float(score)
    logger.info("baseline_evaluation", score=score_val)
    return score_val


def compile_and_save(
    trainset: list[dspy.Example],
    valset: list[dspy.Example],
    output_path: Path = COMPILED_OUTPUT,
) -> float:
    """运行 BootstrapFewShotWithRandomSearch 编译并保存产物。"""
    teleprompter = BootstrapFewShotWithRandomSearch(
        metric=discovery_relevance_metric,
        max_bootstrapped_demos=3,
        num_candidate_programs=6,
        num_threads=8,
    )

    compiled_module = teleprompter.compile(
        FilterRankModule(),
        trainset=trainset,
        valset=valset,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    compiled_module.save(str(output_path))
    logger.info("compiled_module_saved", path=str(output_path))

    evaluator = dspy.Evaluate(
        devset=valset,
        metric=discovery_relevance_metric,
        num_threads=8,
        display_progress=True,
    )
    optimized_score = evaluator(compiled_module)
    score_val = (
        optimized_score.score if hasattr(optimized_score, "score") else float(optimized_score)
    )
    logger.info("optimized_evaluation", score=score_val)
    return score_val


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="Discovery 排序 DSPy 编译")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/discovery_train.jsonl",
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
        evaluate_baseline(FilterRankModule(), valset)
    else:
        compile_and_save(trainset, valset)


if __name__ == "__main__":
    main()
