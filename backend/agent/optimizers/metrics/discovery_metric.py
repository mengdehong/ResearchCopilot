"""Discovery 排序评估指标。

提供两种评估维度:
1. discovery_relevance_metric — 单样本 Margin Ranking 评分，供 DSPy 编译使用。
2. compute_ndcg_at_k — 批量 nDCG@K 报告，脱离 DSPy 用于离线评估看板。
"""

import math


def discovery_relevance_metric(
    example: object,
    pred: object,
    trace: object = None,
) -> float:
    """基于用户隐式反馈的 Margin Ranking 评分。

    评分逻辑：
    - 被用户选中的论文(is_selected=True): LLM 评分越接近 1 则得分越高。
    - 未被选中的论文(is_selected=False): LLM 评分越接近 0 则得分越高。

    Args:
        example: DSPy Example，含 is_selected 字段。
        pred: 模型预测的 DSPy Example，含 evaluation.relevance_score。
        trace: DSPy trace（编译时用，此处忽略）。

    Returns:
        0.0 ~ 1.0 的得分。
    """
    # DSPy v3: pred 可能是 Prediction(evaluation=...) 也可能是直接的 RelevanceCard
    if hasattr(pred, "evaluation"):
        score: float = pred.evaluation.relevance_score  # type: ignore[union-attr]
    elif hasattr(pred, "relevance_score"):
        score = pred.relevance_score  # type: ignore[union-attr]
    else:
        return 0.0
    is_selected: bool = example.is_selected  # type: ignore[union-attr]

    if is_selected:
        return max(0.0, min(1.0, score))
    else:
        return max(0.0, min(1.0, 1.0 - score))


def compute_ndcg_at_k(
    relevance_labels: list[bool],
    predicted_scores: list[float],
    k: int = 5,
) -> float:
    """计算 nDCG@K。

    基于一组预测分值，重排后与理想排序比较。

    Args:
        relevance_labels: 每篇论文是否被用户选中 (True=相关)。
        predicted_scores: 模型对每篇论文的相关性评分。
        k: 截断位置。

    Returns:
        nDCG@K 值，范围 [0.0, 1.0]。
    """
    if not relevance_labels or not predicted_scores:
        return 0.0
    if len(relevance_labels) != len(predicted_scores):
        raise ValueError(
            f"relevance_labels ({len(relevance_labels)}) 和 "
            f"predicted_scores ({len(predicted_scores)}) 长度不匹配"
        )

    n = min(k, len(relevance_labels))

    # 按预测分降序排列
    paired = sorted(
        zip(predicted_scores, relevance_labels, strict=True),
        key=lambda x: x[0],
        reverse=True,
    )

    dcg = sum((1.0 if paired[i][1] else 0.0) / math.log2(i + 2) for i in range(n))

    # 理想排列: 所有正例排在前面
    ideal_labels = sorted(relevance_labels, reverse=True)
    idcg = sum((1.0 if ideal_labels[i] else 0.0) / math.log2(i + 2) for i in range(n))

    if idcg == 0.0:
        return 0.0

    ndcg = dcg / idcg
    return ndcg
