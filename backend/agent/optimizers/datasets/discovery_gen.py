"""Discovery 排序合成数据生成器（冷启动阶段）。

用模板生成模拟的论文检索场景和用户选择偏好，格式与 discovery_extract.py 输出一致。
"""

import random

from backend.core.logger import get_logger

logger = get_logger(__name__)


TOPICS = [
    ("transformer attention mechanisms", "computer_science"),
    ("diffusion models for image generation", "computer_science"),
    ("graph neural networks for molecular property prediction", "chemistry"),
    ("protein structure prediction with deep learning", "biology"),
    ("reinforcement learning from human feedback", "computer_science"),
    ("neural architecture search", "computer_science"),
    ("federated learning for healthcare", "biology"),
    ("large language model alignment", "computer_science"),
    ("quantum computing algorithms", "physics"),
    ("knowledge graph embedding", "computer_science"),
]

# 典型论文模板 (title_template, abstract_template, is_relevant_to_topic)
PAPER_TEMPLATES: list[tuple[str, str, bool]] = [
    # 高相关
    (
        "A Novel Approach to {topic}: {method}",
        "We propose a new method for {topic} that achieves state-of-the-art results. "
        "Our approach combines {method} with {technique}, showing significant improvements "
        "over existing baselines on standard benchmarks.",
        True,
    ),
    (
        "Survey of Recent Advances in {topic}",
        "This comprehensive survey reviews the latest developments in {topic}. "
        "We categorize existing approaches, analyze their strengths and limitations, "
        "and identify promising future research directions.",
        True,
    ),
    (
        "{topic}: From Theory to Practice",
        "We present a practical framework for {topic} that bridges the gap between "
        "theoretical results and real-world applications. Our experiments on "
        "large-scale datasets demonstrate the effectiveness of the proposed approach.",
        True,
    ),
    # 低相关
    (
        "Optimization Methods for Large-Scale {unrelated}",
        "This paper studies optimization techniques for {unrelated}. "
        "We develop a novel algorithm that converges faster than existing methods. "
        "Experiments on synthetic and real datasets validate our theoretical analysis.",
        False,
    ),
    (
        "A Statistical Analysis of {unrelated} Data",
        "We present a statistical framework for analyzing {unrelated} data. "
        "Our method provides rigorous confidence intervals and hypothesis tests "
        "for common data analysis tasks in this domain.",
        False,
    ),
    (
        "Hardware Acceleration for {unrelated} Workloads",
        "We design specialized hardware accelerators for {unrelated} computations. "
        "Our FPGA-based implementation achieves 10x speedup compared to GPU baselines "
        "while consuming 5x less energy.",
        False,
    ),
]

METHODS = [
    "contrastive learning",
    "variational inference",
    "attention mechanisms",
    "meta-learning",
    "self-supervised pretraining",
]

TECHNIQUES = [
    "knowledge distillation",
    "data augmentation",
    "curriculum learning",
    "multi-task learning",
    "ensemble methods",
]

UNRELATED_TOPICS = [
    "supply chain management",
    "urban traffic flow",
    "social media sentiment",
    "geological survey",
    "agricultural yield",
]


def generate_discovery_dataset(
    total: int = 100,
    seed: int = 42,
) -> list[dict[str, str | float | bool]]:
    """生成 Discovery 排序合成数据集。

    每个样本包含一篇论文及其是否被用户选中。
    正负比例约 3:7（模拟真实场景用户只选少数论文）。

    Args:
        total: 总样本数。
        seed: 随机种子。

    Returns:
        合成样本列表。
    """
    random.seed(seed)
    dataset: list[dict[str, str | float | bool]] = []

    for _ in range(total):
        topic_text, discipline = random.choice(TOPICS)
        template = random.choice(PAPER_TEMPLATES)
        title_tmpl, abstract_tmpl, is_relevant = template

        method = random.choice(METHODS)
        technique = random.choice(TECHNIQUES)
        unrelated = random.choice(UNRELATED_TOPICS)

        title = title_tmpl.format(topic=topic_text, method=method, unrelated=unrelated)
        abstract = abstract_tmpl.format(
            topic=topic_text,
            method=method,
            technique=technique,
            unrelated=unrelated,
        )

        # 相关论文有 70% 概率被选中，不相关论文有 10% 概率被选中
        is_selected = random.random() < 0.7 if is_relevant else random.random() < 0.1

        dataset.append(
            {
                "discipline": discipline,
                "user_search_intent": f"Find recent papers about {topic_text}",
                "paper_title": title,
                "paper_abstract": abstract,
                "is_selected": is_selected,
            }
        )

    pos = sum(1 for d in dataset if d["is_selected"])
    logger.info(
        "discovery_synthetic_generated",
        total=len(dataset),
        positive=pos,
        negative=len(dataset) - pos,
    )
    return dataset
