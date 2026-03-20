"""RAG 检索引擎。向量+关键词混合检索、RRF 融合、Reranker 精排。"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder, SentenceTransformer

logger = get_logger(__name__)


class QueryIntent(StrEnum):
    DOCUMENT_LEVEL = "document_level"
    EVIDENCE_LEVEL = "evidence_level"
    CROSS_DOC = "cross_doc"


@dataclass(frozen=True)
class RetrievalQuery:
    """检索请求。"""

    query_text: str
    workspace_id: uuid.UUID
    intent: QueryIntent = QueryIntent.EVIDENCE_LEVEL
    document_ids: list[uuid.UUID] | None = None
    top_k_coarse: int = 30
    top_n_final: int = 8


@dataclass(frozen=True)
class RetrievedChunk:
    """检索结果。"""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content_text: str
    content_type: str
    section_path: str
    page_numbers: list[int]
    score: float
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalTarget:
    """单个检索目标表的 SQL 映射。"""

    name: str
    table_name: str
    content_type: str
    content_expr: str
    section_expr: str
    page_numbers_expr: str
    keyword_expr: str
    metadata_select: str


class RetrievalRow(Protocol):
    """统一检索结果行。"""

    id: uuid.UUID
    document_id: uuid.UUID
    content_text: str
    section_path: str
    page_numbers: list[int] | None
    score: float
    summary_content_type: str | None
    table_title: str | None
    raw_data: dict[str, object] | None
    schema_data: dict[str, object] | None


class RAGEngine:
    """RAG 检索引擎。"""

    def __init__(
        self,
        *,
        embedding_model_name: str = "BAAI/bge-m3",
        reranker_model_name: str = "BAAI/bge-reranker-v2-m3",
    ) -> None:
        self._embedding_model_name = embedding_model_name
        self._reranker_model_name = reranker_model_name
        self._embedder: SentenceTransformer | None = None
        self._reranker: CrossEncoder | None = None

    def _get_embedder(self) -> "SentenceTransformer":
        """延迟加载 Embedding 模型。"""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self._embedding_model_name)
        return self._embedder

    def _get_reranker(self) -> "CrossEncoder":
        """延迟加载 Reranker 模型。"""
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(self._reranker_model_name)
        return self._reranker

    def embed_text(self, text_input: str) -> list[float]:
        """生成文本向量。"""
        embedder = self._get_embedder()
        return list(embedder.encode(text_input))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。"""
        embedder = self._get_embedder()
        return [list(item) for item in embedder.encode(texts)]

    async def retrieve(
        self,
        query: RetrievalQuery,
        session: AsyncSession,
    ) -> list[RetrievedChunk]:
        """按意图路由检索, 再经 reranker 精排。"""
        start = time.monotonic()
        logger.info(
            "rag_retrieve_start",
            intent=query.intent,
            workspace_id=str(query.workspace_id),
            document_ids_count=len(query.document_ids) if query.document_ids else 0,
            top_k_coarse=query.top_k_coarse,
            top_n_final=query.top_n_final,
        )
        query_embedding = self.embed_text(query.query_text)

        if query.intent is QueryIntent.CROSS_DOC:
            candidate_document_ids = await self._retrieve_cross_doc_candidates(
                session=session,
                query=query,
                query_embedding=query_embedding,
            )
            if not candidate_document_ids:
                return []
            evidence_query = replace(query, document_ids=candidate_document_ids)
            evidence_targets = self._get_retrieval_targets(QueryIntent.EVIDENCE_LEVEL)
            coarse_results = await self._search_targets(
                session=session,
                query=evidence_query,
                targets=evidence_targets,
                query_embedding=query_embedding,
            )
        else:
            targets = self._get_retrieval_targets(query.intent)
            coarse_results = await self._search_targets(
                session=session,
                query=query,
                targets=targets,
                query_embedding=query_embedding,
            )

        final_results = self._rerank(query.query_text, coarse_results, query.top_n_final)
        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "rag_retrieve_complete",
            intent=query.intent,
            workspace_id=str(query.workspace_id),
            coarse_count=len(coarse_results),
            final_count=len(final_results),
            duration_ms=duration_ms,
        )
        return final_results

    def _get_retrieval_targets(self, intent: QueryIntent) -> list[RetrievalTarget]:
        """根据查询意图选择检索目标。"""
        if intent is QueryIntent.DOCUMENT_LEVEL:
            return [self._doc_summary_target()]
        if intent is QueryIntent.EVIDENCE_LEVEL:
            return [self._paragraph_target(), self._table_target()]
        if intent is QueryIntent.CROSS_DOC:
            return [self._doc_summary_target()]
        raise ValueError(f"Unsupported query intent: {intent}")

    async def _retrieve_cross_doc_candidates(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
        query_embedding: list[float],
    ) -> list[uuid.UUID]:
        """先从文档摘要中选候选文档, 再进入证据检索。"""
        summary_target = self._doc_summary_target()
        summary_results = await self._search_target(
            session=session,
            query=query,
            target=summary_target,
            query_embedding=query_embedding,
        )
        seen_document_ids: set[uuid.UUID] = set()
        candidate_document_ids: list[uuid.UUID] = []
        for chunk in summary_results:
            if chunk.document_id in seen_document_ids:
                continue
            seen_document_ids.add(chunk.document_id)
            candidate_document_ids.append(chunk.document_id)
        return candidate_document_ids

    async def _search_targets(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
        targets: list[RetrievalTarget],
        query_embedding: list[float],
    ) -> list[RetrievedChunk]:
        """执行多个目标表检索并合并结果。"""
        target_results = await asyncio.gather(
            *[
                self._search_target(
                    session=session,
                    query=query,
                    target=target,
                    query_embedding=query_embedding,
                )
                for target in targets
            ]
        )
        merged_results: list[RetrievedChunk] = []
        for result in target_results:
            merged_results.extend(result)
        return merged_results

    async def _search_target(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
        target: RetrievalTarget,
        query_embedding: list[float],
    ) -> list[RetrievedChunk]:
        """对单个目标表执行混合检索。"""
        vector_results, keyword_results = await asyncio.gather(
            self._vector_search_target(
                session=session,
                query=query,
                target=target,
                query_embedding=query_embedding,
            ),
            self._keyword_search_target(
                session=session,
                query=query,
                target=target,
            ),
        )
        return self._rrf_merge(vector_results, keyword_results, k=60)

    async def _vector_search_target(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
        target: RetrievalTarget,
        query_embedding: list[float],
    ) -> list[RetrievedChunk]:
        """在指定目标表上执行向量检索。"""
        sql = text(
            f"""
            SELECT
                id,
                document_id,
                {target.content_expr} AS content_text,
                {target.section_expr} AS section_path,
                {target.page_numbers_expr} AS page_numbers,
                {target.metadata_select},
                1 - (embedding <=> :embedding) AS score
            FROM {target.table_name}
            WHERE embedding IS NOT NULL
              AND document_id IN (
                SELECT id FROM documents
                WHERE workspace_id = :workspace_id
              ) {self._build_document_filter(query.document_ids)}
            ORDER BY embedding <=> :embedding
            LIMIT :limit
            """
        )
        result = await session.execute(
            sql,
            {
                "embedding": str(query_embedding),
                "workspace_id": str(query.workspace_id),
                "limit": query.top_k_coarse,
            },
        )
        return [self._map_row_to_chunk(row=row, target=target) for row in result.fetchall()]

    async def _keyword_search_target(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
        target: RetrievalTarget,
    ) -> list[RetrievedChunk]:
        """在指定目标表上执行全文检索。"""
        sql = text(
            f"""
            SELECT
                id,
                document_id,
                {target.content_expr} AS content_text,
                {target.section_expr} AS section_path,
                {target.page_numbers_expr} AS page_numbers,
                {target.metadata_select},
                ts_rank(
                    to_tsvector('english', {target.keyword_expr}),
                    plainto_tsquery('english', :query)
                ) AS score
            FROM {target.table_name}
            WHERE document_id IN (
                SELECT id FROM documents
                WHERE workspace_id = :workspace_id
              ) {self._build_document_filter(query.document_ids)}
              AND to_tsvector('english', {target.keyword_expr})
                @@ plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        result = await session.execute(
            sql,
            {
                "query": query.query_text,
                "workspace_id": str(query.workspace_id),
                "limit": query.top_k_coarse,
            },
        )
        return [self._map_row_to_chunk(row=row, target=target) for row in result.fetchall()]

    def _rerank(
        self,
        query_text: str,
        chunks: list[RetrievedChunk],
        top_n: int,
    ) -> list[RetrievedChunk]:
        """对粗召回结果做 cross-encoder 精排。"""
        if not chunks:
            return []
        reranker = self._get_reranker()
        scores = list(reranker.predict([(query_text, chunk.content_text) for chunk in chunks]))
        reranked = sorted(
            [
                replace(chunk, score=float(score))
                for chunk, score in zip(chunks, scores, strict=True)
            ],
            key=lambda chunk: chunk.score,
            reverse=True,
        )
        return reranked[:top_n]

    @staticmethod
    def _build_document_filter(document_ids: list[uuid.UUID] | None) -> str:
        """构建可选的 document_id SQL 过滤片段。"""
        if not document_ids:
            return ""
        joined_ids = ",".join(f"'{document_id!s}'" for document_id in document_ids)
        return f" AND document_id IN ({joined_ids})"

    def _map_row_to_chunk(self, row: object, target: RetrievalTarget) -> RetrievedChunk:
        """将 SQL 结果映射为统一检索结果。"""
        typed_row = cast("RetrievalRow", row)
        row_page_numbers = typed_row.page_numbers
        page_numbers = [] if row_page_numbers is None else list(row_page_numbers)
        metadata: dict[str, object] = {}
        if target.name == "doc_summaries":
            summary_content_type = typed_row.summary_content_type
            if summary_content_type is not None:
                metadata["summary_content_type"] = summary_content_type
        if target.name == "tables":
            metadata["table_title"] = typed_row.table_title
            metadata["raw_data"] = typed_row.raw_data
            schema_data = typed_row.schema_data
            if schema_data is not None:
                metadata["schema_data"] = schema_data
        return RetrievedChunk(
            chunk_id=typed_row.id,
            document_id=typed_row.document_id,
            content_text=typed_row.content_text,
            content_type=target.content_type,
            section_path=typed_row.section_path,
            page_numbers=page_numbers,
            score=float(typed_row.score),
            metadata=metadata,
        )

    @staticmethod
    def _doc_summary_target() -> RetrievalTarget:
        return RetrievalTarget(
            name="doc_summaries",
            table_name="doc_summaries",
            content_type="doc_summary",
            content_expr="content_text",
            section_expr="''",
            page_numbers_expr="ARRAY[]::integer[]",
            keyword_expr="content_text",
            metadata_select=(
                "content_type AS summary_content_type, "
                "NULL::text AS table_title, "
                "NULL::jsonb AS raw_data, "
                "NULL::jsonb AS schema_data"
            ),
        )

    @staticmethod
    def _paragraph_target() -> RetrievalTarget:
        return RetrievalTarget(
            name="paragraphs",
            table_name="paragraphs",
            content_type="paragraph",
            content_expr="content_text",
            section_expr="section_path",
            page_numbers_expr="page_numbers",
            keyword_expr="content_text",
            metadata_select=(
                "NULL::text AS summary_content_type, "
                "NULL::text AS table_title, "
                "NULL::jsonb AS raw_data, "
                "NULL::jsonb AS schema_data"
            ),
        )

    @staticmethod
    def _table_target() -> RetrievalTarget:
        table_text_expr = "COALESCE(summary_text, table_title)"
        return RetrievalTarget(
            name="tables",
            table_name="tables",
            content_type="table",
            content_expr=table_text_expr,
            section_expr="section_path",
            page_numbers_expr="ARRAY[page_number]",
            keyword_expr=table_text_expr,
            metadata_select=(
                "NULL::text AS summary_content_type, "
                "table_title AS table_title, "
                "raw_data AS raw_data, "
                "schema_data AS schema_data"
            ),
        )

    @staticmethod
    def _rrf_merge(
        list_a: list[RetrievedChunk],
        list_b: list[RetrievedChunk],
        *,
        k: int = 60,
    ) -> list[RetrievedChunk]:
        """Reciprocal Rank Fusion 合并排序。"""
        scores: dict[uuid.UUID, float] = {}
        chunks: dict[uuid.UUID, RetrievedChunk] = {}

        for rank, chunk in enumerate(list_a):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1 / (k + rank + 1)
            chunks[chunk.chunk_id] = chunk

        for rank, chunk in enumerate(list_b):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1 / (k + rank + 1)
            chunks[chunk.chunk_id] = chunk

        sorted_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=chunks[chunk_id].document_id,
                content_text=chunks[chunk_id].content_text,
                content_type=chunks[chunk_id].content_type,
                section_path=chunks[chunk_id].section_path,
                page_numbers=chunks[chunk_id].page_numbers,
                score=scores[chunk_id],
                metadata=chunks[chunk_id].metadata,
            )
            for chunk_id in sorted_ids
        ]
