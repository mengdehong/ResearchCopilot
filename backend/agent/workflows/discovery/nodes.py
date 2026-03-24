"""Discovery WF 节点函数。寻源初筛：扩展查询 → 搜索 → 筛选排序 → HITL 勾选 → 触发 ingestion → 写 artifacts。"""

import json
from concurrent.futures import ThreadPoolExecutor

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
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
    category: str | None = None  # ArXiv 分类号（如 cs.CL）


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

    logger.info("expand_query_done", query_count=len(result.queries), category=result.category)
    return {"search_queries": result.queries, "search_category": result.category}


def search_apis(state: DiscoveryState) -> dict:
    """调 ArXiv API 搜索论文。"""
    queries = state.get("search_queries", [])
    category = state.get("search_category")
    raw_results: list[dict] = []

    for query in queries:
        try:
            invoke_args: dict = {"query": query, "max_results": 15}
            if category:
                invoke_args["category"] = category
            papers = search_arxiv.invoke(invoke_args)
            raw_results.extend(papers)
            logger.info("search_api_call", query=query, source="arxiv", count=len(papers))
        except Exception:
            logger.warning("search_api_failed", query=query, source="arxiv")
            raise

    logger.info("search_apis_done", total_raw=len(raw_results))
    return {"raw_results": raw_results}


def filter_and_rank(
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

    def _evaluate_paper(paper: dict) -> PaperCard | None:
        try:
            dspy_module = dspy_registry.get("filter_rank")
            if dspy_module is not None:
                result = dspy_module(
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
                        "user_message": user_message,
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

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_evaluate_paper, p) for p in unique]
        results = [f.result() for f in futures]

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
    if not isinstance(response, dict):
        response = {}
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

        try:
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
        finally:
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


_INGESTION_POLL_INTERVAL_S = 5
_INGESTION_TIMEOUT_S = 600  # 10 分钟


def trigger_ingestion(state: DiscoveryState, config: RunnableConfig) -> dict:
    """对选中论文触发 ingestion pipeline。

    通过 httpx 调用 BFF from-arxiv 端点下载 PDF 并触发 Celery 解析。
    返回 ingestion_task_ids 为 document_id 列表（用于后续轮询状态）。
    """
    selected_ids = state.get("selected_paper_ids", [])
    candidate_papers = state.get("candidate_papers", [])
    workspace_id = state.get("workspace_id", "")

    configurable = config.get("configurable", {})
    bff_base_url = configurable.get("bff_base_url", "http://localhost:8000")
    thread_id = configurable.get("thread_id")
    run_id = configurable.get("run_id")
    auth_token = configurable.get("auth_token")

    # 构建 arxiv_id -> title 映射
    title_map: dict[str, str] = {}
    for paper in candidate_papers:
        paper_obj = paper if isinstance(paper, dict) else paper.model_dump()
        title_map[paper_obj.get("arxiv_id", "")] = paper_obj.get("title", "")

    task_ids: list[str] = []

    for paper_id in selected_ids:
        try:
            params: dict[str, str] = {
                "arxiv_id": paper_id,
                "workspace_id": str(workspace_id),
            }
            title = title_map.get(paper_id)
            if title:
                params["title"] = title
            if thread_id and run_id:
                params["thread_id"] = str(thread_id)
                params["run_id"] = str(run_id)

            headers: dict[str, str] = {}
            if auth_token:
                headers["Authorization"] = auth_token

            resp = httpx.post(
                f"{bff_base_url}/api/v1/documents/from-arxiv",
                params=params,
                headers=headers,
                timeout=90.0,  # ArXiv PDF 下载可能较慢
            )
            resp.raise_for_status()
            doc_id = resp.json().get("id", paper_id)
            task_ids.append(str(doc_id))
            logger.info(
                "trigger_ingestion_paper", paper_id=paper_id, document_id=doc_id, status="ok"
            )
        except httpx.HTTPError:
            logger.warning("trigger_ingestion_failed", paper_id=paper_id)
            task_ids.append(f"failed_{paper_id}")

    logger.info("trigger_ingestion_done", task_count=len(task_ids))
    return {"ingestion_task_ids": task_ids}


def wait_for_ingestion(state: DiscoveryState, config: RunnableConfig) -> dict:
    """轮询等待所有文档解析完成（completed / failed）。

    不使用 interrupt，保持图执行和 SSE 流活跃。
    每 5 秒轮询一次 BFF /documents/{id}/status 端点，
    超时 10 分钟后自动放弃等待。
    """
    import time

    task_ids = state.get("ingestion_task_ids", [])
    if not task_ids:
        return {}

    # 过滤掉触发失败的 task
    valid_ids = [tid for tid in task_ids if not tid.startswith("failed_")]
    if not valid_ids:
        logger.warning("wait_for_ingestion_no_valid_tasks")
        return {}

    bff_base_url = state.get("bff_base_url", "http://localhost:8000")
    configurable = config.get("configurable", {})
    auth_token = configurable.get("auth_token")
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = auth_token

    pending: set[str] = set(valid_ids)
    results: dict[str, str] = {}
    deadline = time.monotonic() + _INGESTION_TIMEOUT_S

    logger.info("wait_for_ingestion_start", doc_ids=valid_ids)

    while pending and time.monotonic() < deadline:
        time.sleep(_INGESTION_POLL_INTERVAL_S)
        for doc_id in list(pending):
            try:
                resp = httpx.get(
                    f"{bff_base_url}/api/v1/documents/{doc_id}/status",
                    headers=headers,
                    timeout=10.0,
                )
                resp.raise_for_status()
                status = resp.json().get("parse_status", "pending")
                if status in ("completed", "failed"):
                    pending.discard(doc_id)
                    results[doc_id] = status
                    logger.info("wait_for_ingestion_done", doc_id=doc_id, status=status)
            except httpx.HTTPError:
                logger.warning("wait_for_ingestion_poll_error", doc_id=doc_id)

    if pending:
        logger.warning("wait_for_ingestion_timeout", timed_out_ids=list(pending))
        for doc_id in pending:
            results[doc_id] = "timeout"

    return {"ingestion_results": results}


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
