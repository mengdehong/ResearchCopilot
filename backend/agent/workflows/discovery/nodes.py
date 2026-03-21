"""Discovery WF 节点函数。寻源初筛：扩展查询 → 搜索 → 筛选排序 → HITL 勾选 → 触发 ingestion → 写 artifacts。"""

import asyncio
import json

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel

from backend.agent.dspy_modules import registry as dspy_registry
from backend.agent.prompts.loader import load_prompt
from backend.agent.state import DiscoveryState, PaperCard
from backend.agent.tools.arxiv_tool import search_arxiv
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
    """调 ArXiv API 搜索论文。"""
    queries = state.get("search_queries", [])
    raw_results: list[dict] = []

    for query in queries:
        try:
            papers = search_arxiv.invoke({"query": query, "max_results": 10})
            raw_results.extend(papers)
            logger.info("search_api_call", query=query, source="arxiv", count=len(papers))
        except Exception:
            logger.warning("search_api_failed", query=query, source="arxiv")
            raise

    logger.info("search_apis_done", total_raw=len(raw_results))
    return {"raw_results": raw_results}


async def filter_and_rank(
    state: DiscoveryState,
    *,
    llm: BaseChatModel,
) -> dict:
    """去重 + LLM 并发生成 relevance_comment 填充 PaperCard 列表。"""
    raw_results = state.get("raw_results", [])
    discipline = state.get("discipline", "")
    # 提取用户搜索意图（DSPy 路径需要）
    user_message = _get_last_user_message(state.get("messages", []))

    # 去重（按 arxiv_id）
    seen: set[str] = set()
    unique: list[dict] = []
    for r in raw_results:
        arxiv_id = r.get("arxiv_id", "")
        if arxiv_id and arxiv_id not in seen:
            seen.add(arxiv_id)
            unique.append(r)

    # 并发 LLM 评估相关性（限制并发 10）
    sem = asyncio.Semaphore(10)

    async def _evaluate_paper(paper: dict) -> PaperCard | None:
        async with sem:
            try:
                dspy_module = dspy_registry.get("filter_rank")
                if dspy_module is not None:
                    result = await asyncio.to_thread(
                        dspy_module,
                        discipline=discipline,
                        user_search_intent=user_message,
                        paper_title=paper.get("title", ""),
                        paper_abstract=paper.get("abstract", ""),
                    )
                    evaluation_score = result.relevance_score
                    evaluation_comment = result.relevance_comment
                else:
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
                    evaluation = await llm.with_structured_output(RelevanceComment).ainvoke(
                        [
                            SystemMessage(content=prompt["system"]),
                            HumanMessage(content=prompt["user"]),
                        ]
                    )
                    evaluation_score = evaluation.relevance_score
                    evaluation_comment = evaluation.relevance_comment
                return PaperCard(
                    arxiv_id=paper.get("arxiv_id", ""),
                    title=paper.get("title", ""),
                    authors=paper.get("authors", []),
                    abstract=paper.get("abstract", ""),
                    year=int(paper.get("year", 0) or 0),
                    citation_count=paper.get("citation_count"),
                    relevance_score=evaluation_score,
                    relevance_comment=evaluation_comment,
                    source=paper.get("source", "unknown"),
                )
            except Exception:
                logger.warning("filter_rank_skip_paper", arxiv_id=paper.get("arxiv_id"))
                return None

    results = await asyncio.gather(*[_evaluate_paper(p) for p in unique])
    candidate_papers = [p for p in results if p is not None]

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

    # HITL 反馈采集：写入业务表供 DSPy 离线训练
    _save_discovery_feedback(
        workspace_id=state.get("workspace_id", ""),
        thread_id=state.get("thread_id", ""),
        user_query=_get_last_user_message(state.get("messages", [])),
        discipline=state.get("discipline", ""),
        candidates=candidates,
        selected_ids=selected_ids,
    )

    logger.info("present_candidates_done", selected_count=len(selected_ids))
    return {"selected_paper_ids": selected_ids}


def _get_last_user_message(messages: list) -> str:
    """提取最后一条用户消息文本。"""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return msg.content or ""
    return ""


def _save_discovery_feedback(
    workspace_id: str,
    thread_id: str,
    user_query: str,
    discipline: str,
    candidates: list[PaperCard],
    selected_ids: list[str],
) -> None:
    """将 HITL 选择写入 discovery_feedback 业务表。

    使用 fire-and-forget 模式，写入失败仅记录警告，不影响主流程。
    """
    try:
        # 延迟导入避免循环依赖和运行时 DB session 创建
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from backend.core.config import get_settings
        from backend.models.discovery_feedback import DiscoveryFeedback

        settings = get_settings()
        sync_url = str(settings.database_url).replace("postgresql+asyncpg", "postgresql+psycopg")
        engine = create_engine(sync_url)

        candidates_json = json.dumps(
            [
                {
                    "arxiv_id": p.arxiv_id,
                    "title": p.title,
                    "abstract": p.abstract,
                }
                for p in candidates
            ],
            ensure_ascii=False,
        )

        with Session(engine) as session:
            feedback = DiscoveryFeedback(
                workspace_id=workspace_id,
                thread_id=thread_id,
                user_query=user_query,
                discipline=discipline,
                candidates_json=candidates_json,
                selected_paper_ids=json.dumps(selected_ids),
            )
            session.add(feedback)
            session.commit()

        engine.dispose()

        logger.info(
            "discovery_feedback_saved",
            workspace_id=workspace_id,
            selected_count=len(selected_ids),
        )
    except Exception:
        logger.warning(
            "discovery_feedback_save_failed",
            workspace_id=workspace_id,
        )


def trigger_ingestion(state: DiscoveryState) -> dict:
    """对选中论文触发 ingestion pipeline。

    通过 httpx 调用 BFF document confirm 端点触发 Celery 解析。
    """
    selected_ids = state.get("selected_paper_ids", [])
    bff_base_url = state.get("bff_base_url", "http://localhost:8000")
    task_ids: list[str] = []

    for paper_id in selected_ids:
        try:
            resp = httpx.post(
                f"{bff_base_url}/api/documents/confirm",
                params={"document_id": paper_id},
                timeout=10.0,
            )
            resp.raise_for_status()
            task_ids.append(paper_id)
            logger.info("trigger_ingestion_paper", paper_id=paper_id, status="ok")
        except httpx.HTTPError:
            logger.warning("trigger_ingestion_failed", paper_id=paper_id)
            task_ids.append(f"failed_{paper_id}")

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
