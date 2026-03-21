"""Discovery 排序 DSPy Module。将论文相关性评分抽象为可编译的 DSPy Signature + Module。"""

try:
    import dspy
except ImportError as exc:
    raise ImportError(
        "dspy is required for optimization modules. Install with: uv sync --extra optimization"
    ) from exc

from pydantic import BaseModel


class RelevanceCard(BaseModel):
    """单篇论文的相关性评估结果。"""

    relevance_score: float
    relevance_comment: str


class PaperRankingSignature(dspy.Signature):
    """评估单篇学术论文与用户的初始研究查询的匹配程度并打分 (0.0 到 1.0)。
    你需要给出一个精炼的相关性评价，指出它在哪个维度上契合查询。"""

    discipline: str = dspy.InputField()
    user_search_intent: str = dspy.InputField(desc="用户原始的搜索表达及上下文")
    paper_title: str = dspy.InputField()
    paper_abstract: str = dspy.InputField()

    evaluation: RelevanceCard = dspy.OutputField()


class FilterRankModule(dspy.Module):
    """论文相关性评分模块。使用 Predict（非 CoT）以保持低延迟高并发。"""

    def __init__(self) -> None:
        super().__init__()
        self.prog = dspy.Predict(PaperRankingSignature)

    def forward(
        self,
        discipline: str,
        user_search_intent: str,
        paper_title: str,
        paper_abstract: str,
    ) -> RelevanceCard:
        result = self.prog(
            discipline=discipline,
            user_search_intent=user_search_intent,
            paper_title=paper_title,
            paper_abstract=paper_abstract,
        )
        return result.evaluation
