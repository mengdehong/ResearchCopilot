"""文档解析 Celery 任务。四阶段管道: 解析→分类→LLM增强→Embedding入库。"""
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

from backend.core.logger import get_logger
from backend.services.parser_engine import ParsedDocument, ParseQuality
from backend.workers.tasks.content_classifier import ClassifiedContent, classify_content

logger = get_logger(__name__)


class PdfParserLike(Protocol):
    """parser_engine.PdfParser 兼容接口。"""

    def parse(self, pdf_path: Path) -> ParsedDocument: ...


class RAGEngineLike(Protocol):
    """rag_engine.RAGEngine 部分接口。"""

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


# 类型别名
UpdateStatusFn = Callable[[uuid.UUID, str], Awaitable[None]]
GetFilePathFn = Callable[[uuid.UUID], Awaitable[str]]
LLMEnhancerFn = Callable[[ClassifiedContent], Awaitable[ClassifiedContent]]


async def run_parse_pipeline(
    *,
    doc_id: uuid.UUID,
    update_status: UpdateStatusFn,
    get_file_path: GetFilePathFn,
    parser: PdfParserLike,
    rag_engine: RAGEngineLike,
    session: object,
    fallback_parser: PdfParserLike | None = None,
    llm_enhancer: LLMEnhancerFn | None = None,
) -> None:
    """四阶段文档解析管道。

    Args:
        doc_id: 文档 UUID
        update_status: 状态回写回调
        get_file_path: 获取文件路径回调
        parser: 主 PDF 解析器
        rag_engine: RAG 引擎 (embed_texts)
        session: 数据库 session
        fallback_parser: 降级解析器 (可选)
        llm_enhancer: LLM 语义增强回调 (可选, 失败不阻塞)
    """
    stage_durations: dict[str, float] = {}
    parse_quality: str = ParseQuality.FULL

    await update_status(doc_id, "parsing")

    try:
        # --- Stage 1: 解析 ---
        t0 = time.monotonic()
        file_path = await get_file_path(doc_id)
        parsed = _stage_parse(parser, Path(file_path), fallback_parser)
        parse_quality = parsed.quality
        stage_durations["parse"] = _elapsed_ms(t0)

        # --- Stage 2: 内容分类 ---
        t1 = time.monotonic()
        classified = classify_content(parsed, doc_id)
        stage_durations["classify"] = _elapsed_ms(t1)

        # --- Stage 3: LLM 增强 (可选, 失败不阻塞) ---
        t2 = time.monotonic()
        classified = await _stage_llm_enhance(classified, llm_enhancer)
        stage_durations["enhance"] = _elapsed_ms(t2)

        # --- Stage 4: Embedding + 入库 ---
        t3 = time.monotonic()
        _stage_embed(classified, rag_engine)
        stage_durations["embed"] = _elapsed_ms(t3)

        await update_status(doc_id, "completed")

        total_ms = round(sum(stage_durations.values()))
        logger.info(
            "parse_completed",
            document_id=str(doc_id),
            duration_ms=total_ms,
            stage_durations=stage_durations,
            chunk_counts={
                "doc_summaries": len(classified.doc_summaries),
                "paragraphs": len(classified.paragraphs),
                "tables": len(classified.tables),
                "figures": len(classified.figures),
                "equations": len(classified.equations),
            },
            parse_quality=parse_quality,
        )

    except Exception as exc:
        await update_status(doc_id, "failed")
        logger.error("parse_failed", document_id=str(doc_id), error=str(exc))
        raise


def _stage_parse(
    parser: PdfParserLike,
    pdf_path: Path,
    fallback_parser: PdfParserLike | None,
) -> ParsedDocument:
    """Stage 1: 解析 PDF, 主解析器失败时尝试 fallback。"""
    try:
        return parser.parse(pdf_path)
    except Exception:
        if fallback_parser is None:
            raise
        logger.warning("primary_parser_failed_using_fallback", path=str(pdf_path))
        return fallback_parser.parse(pdf_path)


async def _stage_llm_enhance(
    classified: ClassifiedContent,
    llm_enhancer: LLMEnhancerFn | None,
) -> ClassifiedContent:
    """Stage 3: LLM 语义增强。失败时返回原始分类结果。"""
    if llm_enhancer is None:
        return classified
    try:
        return await llm_enhancer(classified)
    except Exception as exc:
        logger.warning("llm_enhance_failed", error=str(exc))
        return classified


def _stage_embed(
    classified: ClassifiedContent,
    rag_engine: RAGEngineLike,
) -> None:
    """Stage 4: 批量生成 embedding。将向量写回 classified 记录的 embedding 字段。"""
    # 收集所有需要 embedding 的文本
    texts: list[str] = []
    records: list[dict[str, object]] = []

    for rec in classified.doc_summaries:
        raw = rec.get("content_text")
        if raw is not None and raw != "":
            texts.append(str(raw))
            records.append(rec)

    for rec in classified.paragraphs:
        raw = rec.get("content_text")
        if raw is not None and raw != "":
            texts.append(str(raw))
            records.append(rec)

    for rec in classified.tables:
        # 表格用 summary_text 或 table_title 做 embedding
        raw = rec.get("summary_text") or rec.get("table_title")
        if raw is not None and raw != "":
            texts.append(str(raw))
            records.append(rec)

    for rec in classified.figures:
        raw = rec.get("caption_text")
        if raw is not None and raw != "":
            texts.append(str(raw))
            records.append(rec)

    for rec in classified.equations:
        raw = rec.get("context_text")
        if raw is not None and raw != "":
            texts.append(str(raw))
            records.append(rec)

    if not texts:
        return

    embeddings = rag_engine.embed_texts(texts)
    for rec, emb in zip(records, embeddings, strict=True):
        rec["embedding"] = emb


def _elapsed_ms(start: float) -> float:
    """计算从 start 到现在的毫秒数。"""
    return int((time.monotonic() - start) * 10000) / 10.0
