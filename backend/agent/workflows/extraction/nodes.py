"""Extraction WF 节点函数。深度精读：等待 RAG → 增量检查 → 检索 → 生成笔记 → 跨文档对比 → 术语表 → 写 artifacts。"""

import json
import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import ComparisonEntry, ExtractionState, ReadingNote
from backend.core.logger import get_logger
from backend.services.rag_engine import QueryIntent, RAGEngine, RetrievalQuery

logger = get_logger(__name__)


# ── LLM 输出结构 ──


class GeneratedNote(BaseModel):
    """LLM 生成的单篇精读笔记。"""

    key_contributions: list[str]
    methodology: str
    experimental_setup: str
    main_results: str
    limitations: list[str]


class ComparisonResult(BaseModel):
    """LLM 跨文档对比结果。"""

    entries: list[ComparisonEntry]


class GlossaryResult(BaseModel):
    """LLM 生成的术语表。"""

    terms: dict[str, str]


# ── 节点函数 ──


def wait_rag_ready(state: ExtractionState) -> dict:
    """检查上游 Discovery 产出是否就绪。

    当前为占位：检查 artifacts["discovery"]["selected_paper_ids"] 是否存在。
    后续 Phase 接入真实轮询逻辑。
    """
    artifacts = state.get("artifacts", {})
    discovery = artifacts.get("discovery", {})
    paper_ids = discovery.get("selected_paper_ids", [])

    logger.info("wait_rag_ready", paper_count=len(paper_ids))
    return {"paper_ids": paper_ids}


def check_existing_notes(state: ExtractionState) -> dict:
    """增量检查：跳过已有笔记的论文。

    同时检查 in-memory state 和 artifacts 持久层中已有的 reading_notes，
    合并 paper_id 集合后过滤，实现跨多轮 Extraction 调用的增量分析。
    """
    paper_ids = state.get("paper_ids", [])

    # 来源 1: in-memory state（本轮已生成）
    existing_notes = state.get("reading_notes", [])
    existing_ids = {n.paper_id for n in existing_notes}

    # 来源 2: artifacts 持久层（前次运行产出）
    artifact_notes = state.get("artifacts", {}).get("extraction", {}).get("reading_notes", [])
    for note in artifact_notes:
        pid = note.get("paper_id") if isinstance(note, dict) else getattr(note, "paper_id", None)
        if pid:
            existing_ids.add(pid)

    new_ids = [pid for pid in paper_ids if pid not in existing_ids]
    skipped = len(paper_ids) - len(new_ids)
    logger.info(
        "check_existing_notes",
        total=len(paper_ids),
        existing_in_state=len(existing_notes),
        existing_in_artifacts=len(artifact_notes),
        skipped=skipped,
        remaining=len(new_ids),
    )
    return {"paper_ids": new_ids}


async def retrieve_chunks(
    state: ExtractionState,
    *,
    rag_engine: RAGEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict:
    """调 RAG Engine 检索每篇论文的相关段落。

    通过 Discovery artifacts 中的 ingestion_task_ids 将 arxiv_id 映射为 document_id,
    构造 RetrievalQuery 调用 RAGEngine.retrieve() 执行向量+关键词混合检索。
    """
    paper_ids = state.get("paper_ids", [])
    workspace_id = state.get("workspace_id", "")

    if not paper_ids:
        return {"retrieved_chunks": []}

    artifacts = state.get("artifacts", {})
    discovery_papers = artifacts.get("discovery", {}).get("papers", [])
    paper_map = {p["arxiv_id"]: p for p in discovery_papers if "arxiv_id" in p}

    # arxiv_id → document_id 映射 (通过 ingestion_task_ids)
    ingestion_ids = artifacts.get("discovery", {}).get("ingestion_task_ids", [])
    selected_ids = artifacts.get("discovery", {}).get("selected_paper_ids", [])
    arxiv_to_doc: dict[str, str] = {}
    for arxiv_id, doc_id in zip(selected_ids, ingestion_ids, strict=False):
        if not doc_id.startswith("failed_"):
            arxiv_to_doc[arxiv_id] = doc_id

    chunks: list[dict] = []
    async with session_factory() as session:
        for paper_id in paper_ids:
            doc_id_str = arxiv_to_doc.get(paper_id)
            if not doc_id_str:
                logger.warning("retrieve_chunks_no_doc_id", paper_id=paper_id)
                continue

            paper_info = paper_map.get(paper_id, {})
            query_text = paper_info.get("abstract", paper_info.get("title", paper_id))
            query = RetrievalQuery(
                query_text=query_text,
                workspace_id=uuid.UUID(workspace_id),
                intent=QueryIntent.EVIDENCE_LEVEL,
                document_ids=[uuid.UUID(doc_id_str)],
            )

            try:
                paper_chunks = await rag_engine.retrieve(query, session)
                for chunk in paper_chunks:
                    chunks.append(
                        {
                            "paper_id": paper_id,
                            "chunk_id": str(chunk.chunk_id),
                            "content_text": chunk.content_text,
                            "content_type": chunk.content_type,
                            "section_path": chunk.section_path,
                            "page_numbers": chunk.page_numbers,
                            "score": chunk.score,
                        }
                    )
            except Exception:
                logger.warning("retrieve_chunks_failed", paper_id=paper_id)
                raise

    logger.info("retrieve_chunks_done", chunk_count=len(chunks))
    return {"retrieved_chunks": chunks}


def generate_notes(
    state: ExtractionState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 为每篇论文生成结构化精读笔记。

    若 retrieved_chunks 非空，将论文全文段落注入 prompt 以生成深度笔记；
    否则仅基于 abstract 生成初步笔记。
    """
    paper_ids = state.get("paper_ids", [])
    artifacts = state.get("artifacts", {})
    discovery_papers = artifacts.get("discovery", {}).get("papers", [])

    # 构建论文 ID → 信息映射
    paper_map = {p["arxiv_id"]: p for p in discovery_papers if "arxiv_id" in p}

    # 按 paper_id 分组 retrieved_chunks
    retrieved_chunks = state.get("retrieved_chunks", [])
    chunks_by_paper: dict[str, list[dict]] = {}
    for chunk in retrieved_chunks:
        chunks_by_paper.setdefault(chunk["paper_id"], []).append(chunk)

    notes: list[ReadingNote] = list(state.get("reading_notes", []))
    for paper_id in paper_ids:
        paper_info = paper_map.get(paper_id, {})
        paper_chunks = chunks_by_paper.get(paper_id, [])
        chunks_text = "\n---\n".join(c["content_text"] for c in paper_chunks)

        # Critique 打回时携带修订上下文
        revision_context = state.get("revision_context", "")

        human_payload: dict = {
            "paper_id": paper_id,
            "title": paper_info.get("title", ""),
            "abstract": paper_info.get("abstract", ""),
            "full_text_chunks": chunks_text,
        }
        if revision_context:
            human_payload["revision_feedback"] = revision_context

        note_data = llm.with_structured_output(GeneratedNote).invoke(
            [
                SystemMessage(
                    content=load_prompt(
                        "extraction/prompts",
                        key="generate_notes",
                        variables={"paper_json": ""},
                    )["system"]
                ),
                HumanMessage(content=json.dumps(human_payload, ensure_ascii=False)),
            ]
        )
        notes.append(
            ReadingNote(
                paper_id=paper_id,
                key_contributions=note_data.key_contributions,
                methodology=note_data.methodology,
                experimental_setup=note_data.experimental_setup,
                main_results=note_data.main_results,
                limitations=note_data.limitations,
                source_chunks=[c["chunk_id"] for c in paper_chunks],
            )
        )

    logger.info("generate_notes_done", note_count=len(notes))
    return {"reading_notes": notes}


def cross_compare(
    state: ExtractionState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 跨文档对比，输出 ComparisonEntry 列表。"""
    notes = state.get("reading_notes", [])
    if len(notes) < 2:
        logger.info("cross_compare_skip", reason="less_than_2_papers")
        return {"comparison_matrix": []}

    notes_summary = json.dumps(
        [
            {"paper_id": n.paper_id, "methodology": n.methodology, "main_results": n.main_results}
            for n in notes
        ],
        ensure_ascii=False,
    )
    result = llm.with_structured_output(ComparisonResult).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "extraction/prompts",
                    key="cross_compare",
                    variables={"notes_summary": ""},
                )["system"]
            ),
            HumanMessage(content=notes_summary),
        ]
    )

    logger.info("cross_compare_done", entry_count=len(result.entries))
    return {"comparison_matrix": result.entries}


def build_glossary(
    state: ExtractionState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 从精读笔记中构建术语表。"""
    notes = state.get("reading_notes", [])
    notes_text = json.dumps(
        [
            {
                "paper_id": n.paper_id,
                "key_contributions": n.key_contributions,
                "methodology": n.methodology,
            }
            for n in notes
        ],
        ensure_ascii=False,
    )
    result = llm.with_structured_output(GlossaryResult).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "extraction/prompts",
                    key="build_glossary",
                    variables={"notes_text": ""},
                )["system"]
            ),
            HumanMessage(content=notes_text),
        ]
    )

    logger.info("build_glossary_done", term_count=len(result.terms))
    return {"glossary": result.terms}


def write_artifacts(state: ExtractionState) -> dict:
    """将 Extraction 产出物写入 artifacts 命名空间。"""
    return {
        "artifacts": {
            "extraction": {
                "reading_notes": [n.model_dump() for n in state.get("reading_notes", [])],
                "comparison_matrix": [e.model_dump() for e in state.get("comparison_matrix", [])],
                "glossary": state.get("glossary", {}),
            },
        },
    }
