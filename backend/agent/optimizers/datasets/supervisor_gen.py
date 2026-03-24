"""Supervisor 路由合成数据集生成器。

用强模型批量生成路由标注样本，按业务分布先验控制各类别比例。
运行方式: uv run python -m backend.agent.optimizers.datasets.supervisor_gen --output data/supervisor_train.jsonl
"""

import argparse
import json
import random
from pathlib import Path

from backend.core.logger import get_logger

logger = get_logger(__name__)

# 分布先验：类别 → (比例, target_workflow, mode)
CATEGORY_DISTRIBUTION: list[tuple[str, float, str, str]] = [
    ("single_search", 0.25, "discovery", "single"),
    ("single_read", 0.25, "extraction", "single"),
    ("single_code", 0.20, "execution", "single"),
    ("multi_step", 0.20, "", "plan"),
    ("chat", 0.10, "", "chat"),
]

# 各类别的典型用户请求模板
SCENARIO_TEMPLATES: dict[str, list[str]] = {
    "single_search": [
        "帮我搜索关于 {topic} 的最新论文",
        "找一下 {topic} 领域的综述文章",
        "有哪些关于 {topic} 的 2024 年论文？",
        "搜索 {topic} 相关的研究",
        "我想了解 {topic} 的最新进展",
    ],
    "single_read": [
        "帮我精读这篇论文 arxiv:{paper_id}",
        "提取这篇文章的核心方法和实验结果",
        "总结 {paper_id} 的关键贡献",
        "对比分析这几篇论文的方法差异",
        "从已有论文中提取 {topic} 相关的数据表格",
    ],
    "single_code": [
        "帮我实现一个 {topic} 的 baseline 代码",
        "运行这段代码并分析结果:\n```python\nprint('hello')\n```",
        "用 PyTorch 实现 {topic} 的训练脚本",
        "帮我修复这段代码的 bug",
        "生成 {topic} 实验的可视化图表",
    ],
    "multi_step": [
        "帮我完成一个关于 {topic} 的完整研究：先搜索论文，然后精读，最后写综述",
        "我想做一个 {topic} 的实验：先找 baseline 论文，提取方法，然后实现代码",
        "请帮我按顺序完成：搜索 {topic} 文献、提取关键信息、生成对比矩阵",
        "对 {topic} 做一个全面的研究：文献调研 + 方法对比 + 实验设计",
    ],
    "chat": [
        "你好",
        "你能做什么？",
        "谢谢！",
        "请问你支持哪些功能？",
        "你是谁？",
        "这个工具怎么使用？",
    ],
}

TOPICS = [
    "transformer attention mechanisms",
    "diffusion models",
    "graph neural networks",
    "protein structure prediction",
    "reinforcement learning from human feedback",
    "large language model alignment",
    "federated learning",
    "neural architecture search",
    "knowledge graphs",
    "contrastive learning",
]

DISCIPLINES = ["computer_science", "biology", "physics", "mathematics", "chemistry"]


def generate_scenario(
    category: str,
    target_workflow: str,
    mode: str,
) -> dict[str, str | dict]:
    """生成单条合成样本。

    Returns:
        包含 discipline, chat_history, current_artifacts, routing_decision 的字典。
    """
    templates = SCENARIO_TEMPLATES[category]
    template = random.choice(templates)

    topic = random.choice(TOPICS)
    paper_id = f"2401.{random.randint(10000, 99999):05d}"
    user_message = template.format(topic=topic, paper_id=paper_id)

    discipline = random.choice(DISCIPLINES)
    has_artifacts = random.random() > 0.5
    artifacts = json.dumps({"discovery": ["papers"]}) if has_artifacts else "[]"

    routing_decision: dict[str, str | None | dict] = {
        "mode": mode,
        "reasoning": f"用户请求属于 {category} 类别",
    }

    if mode == "single":
        routing_decision["target_workflow"] = target_workflow
        routing_decision["plan"] = None
    elif mode == "plan":
        routing_decision["target_workflow"] = None
        routing_decision["plan"] = {
            "goal": f"完成 {topic} 相关研究",
            "steps": [
                {
                    "workflow": "discovery",
                    "objective": "搜索相关论文",
                    "success_criteria": "找到至少 5 篇相关论文",
                },
                {
                    "workflow": "extraction",
                    "objective": "精读论文",
                    "success_criteria": "提取关键信息",
                },
            ],
        }
    else:  # chat
        routing_decision["target_workflow"] = None
        routing_decision["plan"] = None
        routing_decision["reply_text"] = "你好，我是 Research Copilot。"

    return {
        "discipline": discipline,
        "chat_history": f"Human: {user_message}",
        "current_artifacts": artifacts,
        "routing_decision": routing_decision,
    }


def generate_dataset(total: int = 300, seed: int = 42) -> list[dict[str, str | dict]]:
    """按分布先验生成合成数据集。

    Args:
        total: 总样本数。
        seed: 随机种子。

    Returns:
        合成样本列表。
    """
    random.seed(seed)
    dataset: list[dict[str, str | dict]] = []

    for category, ratio, target_wf, mode in CATEGORY_DISTRIBUTION:
        count = int(total * ratio)
        for _ in range(count):
            dataset.append(generate_scenario(category, target_wf, mode))

    # 补齐可能因 int 截断丢失的样本
    while len(dataset) < total:
        cat, _, tw, m = random.choice(CATEGORY_DISTRIBUTION)
        dataset.append(generate_scenario(cat, tw, m))

    random.shuffle(dataset)
    logger.info("synthetic_dataset_generated", total=len(dataset))
    return dataset


def main() -> None:
    """CLI 入口：生成合成数据并保存为 JSONL。"""
    parser = argparse.ArgumentParser(description="生成 Supervisor 路由合成训练数据")
    parser.add_argument("--output", type=str, required=True, help="输出 JSONL 路径")
    parser.add_argument("--total", type=int, default=300, help="样本总数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    dataset = generate_dataset(total=args.total, seed=args.seed)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for sample in dataset:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    logger.info("dataset_saved", path=str(output_path), count=len(dataset))


if __name__ == "__main__":
    main()
