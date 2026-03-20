"""Extraction WF 节点函数。深度精读：等待 RAG → 增量检查 → 检索 → 生成笔记 → 跨文档对比 → 术语表 → 写 artifacts。"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import ComparisonEntry, ExtractionState, ReadingNote
from backend.core.logger import get_logger

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
    """增量检查：跳过已有笔记的论文。"""
    paper_ids = state.get("paper_ids", [])
    existing_notes = state.get("reading_notes", [])
    existing_ids = {n.paper_id for n in existing_notes}

    new_ids = [pid for pid in paper_ids if pid not in existing_ids]
    logger.info(
        "check_existing_notes",
        total=len(paper_ids),
        skipped=len(paper_ids) - len(new_ids),
    )
    return {"paper_ids": new_ids}


def retrieve_chunks(state: ExtractionState) -> dict:
    """调 RAG Engine 检索相关段落。

    当前为占位实现，返回空 chunks。
    后续 Phase 接入真实 RAGEngine.retrieve()。
    """
    paper_ids = state.get("paper_ids", [])
    # TODO(phase-4): 接入 RAGEngine.retrieve()
    logger.info("retrieve_chunks", paper_count=len(paper_ids))
    return {}


def generate_notes(
    state: ExtractionState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 为每篇论文生成结构化精读笔记。"""
    paper_ids = state.get("paper_ids", [])
    artifacts = state.get("artifacts", {})
    discovery_papers = artifacts.get("discovery", {}).get("papers", [])

    # 构建论文 ID → 信息映射
    paper_map = {p["arxiv_id"]: p for p in discovery_papers if "arxiv_id" in p}

    notes: list[ReadingNote] = list(state.get("reading_notes", []))
    for paper_id in paper_ids:
        paper_info = paper_map.get(paper_id, {})
        note_data = llm.with_structured_output(GeneratedNote).invoke(
            [
                SystemMessage(
                    content=load_prompt(
                        "extraction/prompts",
                        key="generate_notes",
                        variables={"paper_json": ""},
                    )["system"]
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "paper_id": paper_id,
                            "title": paper_info.get("title", ""),
                            "abstract": paper_info.get("abstract", ""),
                        },
                        ensure_ascii=False,
                    )
                ),
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
                source_chunks=[],  # 占位，后续接入 RAG 填充
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
