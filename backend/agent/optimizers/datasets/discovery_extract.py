"""从 discovery_feedback 业务表构建 DSPy 训练数据集。

从数据库读取 HITL 反馈记录，将每条记录拆分为正/负样本对供 DSPy 训练。
运行方式: uv run python -m backend.agent.optimizers.datasets.discovery_extract --output data/discovery_train.jsonl
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger
from backend.models.discovery_feedback import DiscoveryFeedback

logger = get_logger(__name__)


def feedback_to_examples(
    feedback: DiscoveryFeedback,
) -> list[dict[str, str | float | bool]]:
    """将一条 DiscoveryFeedback 拆分为逐篇正/负样本。

    每篇论文对应一条 DSPy Example：
    - 被选中的论文: is_selected=True
    - 未被选中的论文: is_selected=False
    """
    candidates: list[dict[str, str]] = json.loads(feedback.candidates_json)
    selected_ids: list[str] = json.loads(feedback.selected_paper_ids)
    selected_set = set(selected_ids)

    examples: list[dict[str, str | float | bool]] = []
    for paper in candidates:
        paper_id = paper.get("arxiv_id", paper.get("id", ""))
        examples.append(
            {
                "discipline": feedback.discipline,
                "user_search_intent": feedback.user_query,
                "paper_title": paper.get("title", ""),
                "paper_abstract": paper.get("abstract", ""),
                "is_selected": paper_id in selected_set,
            }
        )
    return examples


async def extract_from_db(session: AsyncSession) -> list[dict[str, str | float | bool]]:
    """从数据库读取所有反馈并转换为训练样本列表。"""
    stmt = select(DiscoveryFeedback).order_by(DiscoveryFeedback.created_at)
    result = await session.execute(stmt)
    feedbacks = result.scalars().all()

    all_examples: list[dict[str, str | float | bool]] = []
    for fb in feedbacks:
        all_examples.extend(feedback_to_examples(fb))

    logger.info(
        "discovery_examples_extracted",
        feedback_count=len(feedbacks),
        example_count=len(all_examples),
    )
    return all_examples


def save_examples(
    examples: list[dict[str, str | float | bool]],
    output_path: Path,
) -> None:
    """将样本列表保存为 JSONL 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    logger.info("discovery_examples_saved", path=str(output_path), count=len(examples))


def main() -> None:
    """CLI 入口（同步包装）。"""
    parser = argparse.ArgumentParser(description="从 discovery_feedback 表导出训练数据")
    parser.add_argument("--output", type=str, required=True, help="输出 JSONL 路径")
    args = parser.parse_args()

    import asyncio

    from backend.core.database import get_async_session_factory

    async def _run() -> None:
        session_factory = get_async_session_factory()
        async with session_factory() as session:
            examples = await extract_from_db(session)
            save_examples(examples, Path(args.output))

    asyncio.run(_run())


if __name__ == "__main__":
    main()
