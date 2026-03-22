"""Celery task 入口：文档解析 → 入库 完整管道。

同步 wrapper 调用 async ``run_parse_pipeline``，再将分类结果
持久化到 PostgreSQL 各内容分表（Paragraph / DocSummary / …）。
"""

import asyncio
import uuid
from pathlib import Path

import httpx
import jwt
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.core.logger import get_logger
from backend.models.doc_summary import DocSummary
from backend.models.document import Document
from backend.models.equation import Equation
from backend.models.figure import Figure
from backend.models.paragraph import Paragraph
from backend.models.reference import Reference
from backend.models.section_heading import SectionHeading
from backend.models.table import Table as TableModel
from backend.repositories import base as base_repo
from backend.repositories import document_repo
from backend.services.parser_engine import FallbackParser, MinerUParser
from backend.services.rag_engine import RAGEngine
from backend.workers.celery_app import app
from backend.workers.tasks.content_classifier import ClassifiedContent
from backend.workers.tasks.parse_document import run_parse_pipeline

logger = get_logger(__name__)

# StorageClient 默认 base_dir，保持与 StorageClient 一致
_STORAGE_BASE_DIR = Path("/tmp/research-copilot-uploads")


# ---------------------------------------------------------------------------
# Celery Task
# ---------------------------------------------------------------------------


@app.task(name="tasks.ingest_document", bind=True, max_retries=2)
def ingest_document(
    self: Task, 
    *, 
    doc_id: str, 
    thread_id: str | None = None, 
    run_id: str | None = None
) -> dict[str, str]:
    """文档解析入库入口。Celery 同步 task → asyncio.run 调用 async 管道。"""
    try:
        return asyncio.run(_run_ingest(doc_id, thread_id, run_id))
    except Exception as exc:
        logger.error("ingest_document_failed", doc_id=doc_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc


# ---------------------------------------------------------------------------
# Async 执行核心
# ---------------------------------------------------------------------------


async def _run_ingest(
    doc_id_str: str, 
    thread_id: str | None = None, 
    run_id: str | None = None
) -> dict[str, str]:
    """构造依赖 → 调用四阶段管道 → Stage 5 持久化。"""
    doc_id = uuid.UUID(doc_id_str)
    settings = Settings()

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    parser = MinerUParser()
    fallback_parser = FallbackParser()
    rag_engine = RAGEngine()

    async with session_factory() as session:
        # --- 回调：更新 document.parse_status ---
        async def update_status(did: uuid.UUID, status: str) -> None:
            doc = await base_repo.get_by_id(session, Document, did)
            if doc is not None:
                await document_repo.update_parse_status(session, doc, status)
                await session.commit()

        # --- 回调：获取 PDF 文件路径 ---
        async def get_file_path(did: uuid.UUID) -> str:
            doc = await base_repo.get_by_id(session, Document, did)
            if doc is None:
                raise ValueError(f"Document {did} not found")
            return str(_STORAGE_BASE_DIR / doc.file_path)

        # --- 执行四阶段管道（返回含 embedding 的 ClassifiedContent）---
        classified = await run_parse_pipeline(
            doc_id=doc_id,
            update_status=update_status,
            get_file_path=get_file_path,
            parser=parser,
            rag_engine=rag_engine,
            session=session,
            fallback_parser=fallback_parser,
        )

        # --- Stage 5: 持久化到 PostgreSQL ---
        await _persist_classified_content(session, classified)
        await session.commit()
        
        # --- Stage 6: Webhook Callback to Agent ---
        if thread_id and run_id:
            try:
                secret = settings.internal_token_secret or settings.jwt_secret
                system_token = jwt.encode(
                    {"sub": "system", "role": "system_worker"},
                    secret,
                    algorithm="HS256",
                )
                bff_base_url = settings.internal_api_url
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{bff_base_url}/api/agent/threads/{thread_id}/runs/{run_id}/resume",
                        json={"action": "ingestion_complete", "document_id": doc_id_str},
                        headers={"Authorization": f"Bearer {system_token}"},
                        timeout=5.0,
                    )
                    resp.raise_for_status()
                logger.info("resumed_agent_after_ingestion", thread_id=thread_id, run_id=run_id)
            except Exception as e:
                logger.warning("failed_to_resume_agent", error=str(e), thread_id=thread_id, run_id=run_id)

    await engine.dispose()

    logger.info("ingest_document_completed", doc_id=doc_id_str)
    return {"doc_id": doc_id_str, "status": "completed"}


# ---------------------------------------------------------------------------
# Stage 5: DB 批量写入
# ---------------------------------------------------------------------------


async def _persist_classified_content(
    session: AsyncSession,
    classified: ClassifiedContent,
) -> None:
    """将分类结果批量写入 PostgreSQL 各内容分表。"""
    orm_objects: list[object] = []

    for rec in classified.doc_summaries:
        orm_objects.append(
            DocSummary(
                document_id=rec["document_id"],
                content_type=str(rec["content_type"]),
                content_text=str(rec["content_text"]),
                embedding=rec.get("embedding"),
            )
        )

    for rec in classified.paragraphs:
        orm_objects.append(
            Paragraph(
                document_id=rec["document_id"],
                section_path=str(rec["section_path"]),
                chunk_index=int(rec.get("chunk_index", 0)),  # type: ignore[arg-type]
                content_text=str(rec["content_text"]),
                page_numbers=rec.get("page_numbers"),
                embedding=rec.get("embedding"),
            )
        )

    for rec in classified.tables:
        orm_objects.append(
            TableModel(
                document_id=rec["document_id"],
                section_path=str(rec.get("section_path", "")),
                table_title=str(rec.get("table_title", "")),
                page_number=int(rec.get("page_number", 0)),  # type: ignore[arg-type]
                raw_data=rec.get("raw_data", {}),
                summary_text=rec.get("summary_text"),
                schema_data=rec.get("schema_data"),
                embedding=rec.get("embedding"),
            )
        )

    for rec in classified.figures:
        orm_objects.append(
            Figure(
                document_id=rec["document_id"],
                section_path=str(rec.get("section_path", "")),
                caption_text=str(rec.get("caption_text", "")),
                context_text=str(rec.get("context_text", "")),
                image_path=str(rec.get("image_path", "")),
                page_number=int(rec.get("page_number", 0)),  # type: ignore[arg-type]
                embedding=rec.get("embedding"),
            )
        )

    for rec in classified.equations:
        orm_objects.append(
            Equation(
                document_id=rec["document_id"],
                section_path=str(rec.get("section_path", "")),
                latex_text=str(rec.get("latex_text", "")),
                context_text=str(rec.get("context_text", "")),
                equation_label=rec.get("equation_label"),
                page_number=int(rec.get("page_number", 0)),  # type: ignore[arg-type]
                embedding=rec.get("embedding"),
            )
        )

    for rec in classified.references:
        orm_objects.append(
            Reference(
                document_id=rec["document_id"],
                ref_index=int(rec.get("ref_index", 0)),  # type: ignore[arg-type]
                ref_title=str(rec.get("ref_title", "")),
                ref_authors=rec.get("ref_authors"),
                ref_year=rec.get("ref_year"),
                ref_doi=rec.get("ref_doi"),
            )
        )

    for rec in classified.section_headings:
        orm_objects.append(
            SectionHeading(
                document_id=rec["document_id"],
                level=int(rec.get("level", 1)),  # type: ignore[arg-type]
                heading_text=str(rec.get("heading_text", "")),
                page_number=int(rec.get("page_number", 0)),  # type: ignore[arg-type]
            )
        )

    if orm_objects:
        session.add_all(orm_objects)
        await session.flush()

    logger.info(
        "persist_classified_content",
        total_objects=len(orm_objects),
        doc_summaries=len(classified.doc_summaries),
        paragraphs=len(classified.paragraphs),
        tables=len(classified.tables),
        figures=len(classified.figures),
        equations=len(classified.equations),
        references=len(classified.references),
        section_headings=len(classified.section_headings),
    )
