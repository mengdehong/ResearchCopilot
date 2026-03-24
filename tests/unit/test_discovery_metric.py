"""Discovery 排序评分函数单元测试。"""

from unittest.mock import MagicMock

from backend.agent.optimizers.metrics.discovery_metric import (
    compute_ndcg_at_k,
    discovery_relevance_metric,
)


def _make_example(is_selected: bool) -> MagicMock:
    """创建 DSPy Example mock。"""
    ex = MagicMock()
    ex.is_selected = is_selected
    return ex


def _make_prediction(score: float) -> MagicMock:
    """创建带 evaluation.relevance_score 的 mock。"""
    pred = MagicMock()
    pred.evaluation.relevance_score = score
    return pred


# ── Margin Ranking 测试 ──


def test_selected_high_score_gets_high_metric() -> None:
    """选中论文 + 高 LLM 评分 → 高得分。"""
    example = _make_example(is_selected=True)
    pred = _make_prediction(score=0.9)
    assert discovery_relevance_metric(example, pred) == 0.9


def test_selected_low_score_gets_low_metric() -> None:
    """选中论文 + 低 LLM 评分 → 低得分。"""
    example = _make_example(is_selected=True)
    pred = _make_prediction(score=0.1)
    assert discovery_relevance_metric(example, pred) == 0.1


def test_unselected_low_score_gets_high_metric() -> None:
    """未选中论文 + 低 LLM 评分 → 高得分。"""
    example = _make_example(is_selected=False)
    pred = _make_prediction(score=0.1)
    assert abs(discovery_relevance_metric(example, pred) - 0.9) < 0.001


def test_unselected_high_score_gets_low_metric() -> None:
    """未选中论文 + 高 LLM 评分 → 低得分。"""
    example = _make_example(is_selected=False)
    pred = _make_prediction(score=0.9)
    assert abs(discovery_relevance_metric(example, pred) - 0.1) < 0.001


def test_score_clamped_to_0_1() -> None:
    """评分超出 [0, 1] 范围时被 clamp。"""
    example = _make_example(is_selected=True)
    pred_high = _make_prediction(score=1.5)
    pred_neg = _make_prediction(score=-0.5)
    assert discovery_relevance_metric(example, pred_high) == 1.0
    assert discovery_relevance_metric(example, pred_neg) == 0.0


# ── nDCG@K 测试 ──


def test_ndcg_perfect_ranking() -> None:
    """完美排名: nDCG = 1.0。"""
    labels = [True, True, False, False, False]
    scores = [0.9, 0.8, 0.3, 0.2, 0.1]
    assert compute_ndcg_at_k(labels, scores, k=5) == 1.0


def test_ndcg_worst_ranking() -> None:
    """两个正例排在最后: nDCG < 1.0。"""
    labels = [True, True, False, False, False]
    scores = [0.1, 0.2, 0.7, 0.8, 0.9]
    ndcg = compute_ndcg_at_k(labels, scores, k=5)
    assert ndcg < 1.0
    assert ndcg > 0.0


def test_ndcg_empty_input() -> None:
    """空输入返回 0.0。"""
    assert compute_ndcg_at_k([], [], k=5) == 0.0


def test_ndcg_all_negative() -> None:
    """全部为负例: nDCG = 0.0。"""
    labels = [False, False, False]
    scores = [0.9, 0.5, 0.1]
    assert compute_ndcg_at_k(labels, scores, k=3) == 0.0


def test_ndcg_single_positive_at_top() -> None:
    """唯一正例排第一: nDCG = 1.0。"""
    labels = [True, False, False]
    scores = [0.9, 0.5, 0.1]
    assert compute_ndcg_at_k(labels, scores, k=3) == 1.0
