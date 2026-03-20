"""Discovery WF 节点函数。寻源初筛：扩展查询 → 搜索 → 筛选排序 → HITL 勾选 → 触发 ingestion → 写 artifacts。"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import DiscoveryState, PaperCard
from backend.core.logger import get_logger

logger = get_logger(__name__)


# ── LLM 输出结构 ──


class ExpandedQueries(BaseModel):
    """LLM 扩展后的搜索查询列表。"""

    queries: list[str]


class RelevanceComment(BaseModel):
    """LLM 对单篇论文的相关性评语。"""

    relevance_score: float
    relevance_comment: str


# ── 节点函数 ──


def expand_query(state: DiscoveryState, *, llm: BaseChatModel) -> dict:
    """LLM 扩展用户查询为多个搜索关键词。"""
    messages = state["messages"]
    user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            user_message = msg.content or ""
            break

    discipline = state.get("discipline", "")
    prompt = load_prompt(
        "discovery/prompts",
        key="expand_query",
        variables={
            "discipline": discipline,
            "user_message": user_message,
        },
    )
    result = llm.with_structured_output(ExpandedQueries).invoke(
        [
            SystemMessage(content=prompt["system"]),
            HumanMessage(content=prompt["user"]),
        ]
    )

    logger.info("expand_query_done", query_count=len(result.queries))
    return {"search_queries": result.queries}


def search_apis(state: DiscoveryState) -> dict:
    """调 ArXiv + Semantic Scholar API 搜索论文。

    当前为占位实现，返回空结果列表。
    后续 Phase 替换为真实 API 调用。
    """
    queries = state.get("search_queries", [])
    raw_results: list[dict] = []

    # TODO(phase-4): 接入 ArXiv API + Semantic Scholar API
    # 每个 query 调一次 API，合并去重
    for query in queries:
        logger.info("search_api_call", query=query, source="placeholder")

    logger.info("search_apis_done", total_raw=len(raw_results))
    return {"raw_results": raw_results}


def filter_and_rank(
    state: DiscoveryState,
    *,
    llm: BaseChatModel,
) -> dict:
    """去重 + LLM 生成 relevance_comment 填充 PaperCard 列表。"""
    raw_results = state.get("raw_results", [])
    discipline = state.get("discipline", "")

    # 去重（按 arxiv_id）
    seen: set[str] = set()
    unique: list[dict] = []
    for r in raw_results:
        arxiv_id = r.get("arxiv_id", "")
        if arxiv_id and arxiv_id not in seen:
            seen.add(arxiv_id)
            unique.append(r)

    # LLM 评估相关性
    candidate_papers: list[PaperCard] = []
    for paper in unique:
        try:
            prompt = load_prompt(
                "discovery/prompts",
                key="filter_and_rank",
                variables={
                    "discipline": discipline,
                    "paper_json": json.dumps(
                        {
                            "title": paper.get("title", ""),
                            "abstract": paper.get("abstract", ""),
                        },
                        ensure_ascii=False,
                    ),
                },
            )
            evaluation = llm.with_structured_output(RelevanceComment).invoke(
                [
                    SystemMessage(content=prompt["system"]),
                    HumanMessage(content=prompt["user"]),
                ]
            )
            candidate_papers.append(
                PaperCard(
                    arxiv_id=paper.get("arxiv_id", ""),
                    title=paper.get("title", ""),
                    authors=paper.get("authors", []),
                    abstract=paper.get("abstract", ""),
                    year=paper.get("year", 0),
                    citation_count=paper.get("citation_count"),
                    relevance_score=evaluation.relevance_score,
                    relevance_comment=evaluation.relevance_comment,
                    source=paper.get("source", "unknown"),
                )
            )
        except Exception:
            logger.warning("filter_rank_skip_paper", arxiv_id=paper.get("arxiv_id"))
            raise

    # 按 relevance_score 降序排列
    candidate_papers.sort(key=lambda p: p.relevance_score, reverse=True)

    logger.info(
        "filter_and_rank_done",
        input_count=len(raw_results),
        output_count=len(candidate_papers),
    )
    return {"candidate_papers": candidate_papers}


def present_candidates(state: DiscoveryState) -> dict:
    """独立 HITL 节点：展示候选论文列表，用户勾选要深读的论文。"""
    candidates = state.get("candidate_papers", [])
    response = interrupt(
        {
            "action": "select_papers",
            "candidates": [
                {
                    "id": p.arxiv_id,
                    "title": p.title,
                    "abstract": p.abstract,
                    "year": p.year,
                    "relevance_score": p.relevance_score,
                    "relevance_comment": p.relevance_comment,
                }
                for p in candidates
            ],
        }
    )
    selected_ids: list[str] = response.get("selected_ids", [])
    logger.info("present_candidates_done", selected_count=len(selected_ids))
    return {"selected_paper_ids": selected_ids}


def trigger_ingestion(state: DiscoveryState) -> dict:
    """对选中论文触发 ingestion pipeline。

    当前为占位实现，记录任务 ID 占位。
    后续 Phase 替换为 BFF document service 调用。
    """
    selected_ids = state.get("selected_paper_ids", [])
    # TODO(phase-5): 调 BFF document service 创建 ingestion 任务
    task_ids = [f"task_{paper_id}" for paper_id in selected_ids]
    logger.info("trigger_ingestion_done", task_count=len(task_ids))
    return {"ingestion_task_ids": task_ids}


def write_artifacts(state: DiscoveryState) -> dict:
    """将 Discovery 产出物写入 artifacts 命名空间。"""
    candidate_papers = state.get("candidate_papers", [])
    selected_paper_ids = state.get("selected_paper_ids", [])
    ingestion_task_ids = state.get("ingestion_task_ids", [])
    search_queries = state.get("search_queries", [])
    raw_results = state.get("raw_results", [])

    return {
        "artifacts": {
            "discovery": {
                "papers": [p.model_dump() for p in candidate_papers],
                "selected_paper_ids": selected_paper_ids,
                "ingestion_task_ids": ingestion_task_ids,
                "search_metadata": {
                    "queries": search_queries,
                    "total_raw_results": len(raw_results),
                },
            },
        },
    }
