"""RAG 检索引擎。向量+关键词混合检索、RRF 融合、Reranker 精排。"""
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger

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
    content_type: str  # "paragraph" | "table" | "figure" | "equation"
    section_path: str
    page_numbers: list[int]
    score: float
    metadata: dict[str, object] = field(default_factory=dict)


class RAGEngine:
    """RAG 检索引擎。"""

    def __init__(
        self, *, embedding_model_name: str = "BAAI/bge-m3",
    ) -> None:
        self._embedding_model_name = embedding_model_name
        self._embedder: object | None = None

    def _get_embedder(self) -> object:
        """延迟加载 Embedding 模型。"""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self._embedding_model_name)
        return self._embedder

    def embed_text(self, text_input: str) -> list[float]:
        """生成文本向量。"""
        embedder = self._get_embedder()
        return embedder.encode(text_input).tolist()  # type: ignore[union-attr]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。"""
        embedder = self._get_embedder()
        return embedder.encode(texts).tolist()  # type: ignore[union-attr]

    async def retrieve(
        self,
        query: RetrievalQuery,
        session: AsyncSession,
    ) -> list[RetrievedChunk]:
        """混合检索: 向量 + 关键词 → RRF 融合 → 返回 top-N。"""
        query_embedding = self.embed_text(query.query_text)

        vector_results = await self._vector_search(
            session, query, query_embedding,
        )
        keyword_results = await self._keyword_search(
            session, query,
        )

        fused = self._rrf_merge(vector_results, keyword_results, k=60)
        return fused[:query.top_n_final]

    async def _vector_search(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
        query_embedding: list[float],
    ) -> list[RetrievedChunk]:
        """pgvector cosine similarity 检索。"""
        embedding_str = str(query_embedding)
        doc_filter = ""
        if query.document_ids:
            ids = ",".join(f"'{d!s}'" for d in query.document_ids)
            doc_filter = f"AND document_id IN ({ids})"

        sql = text(f"""
            SELECT id, document_id, content_text, section_path,
                   page_numbers,
                   1 - (embedding <=> :embedding) AS score
            FROM paragraphs
            WHERE document_id IN (
                SELECT id FROM documents
                WHERE workspace_id = :workspace_id
            ) {doc_filter}
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)
        result = await session.execute(sql, {
            "embedding": embedding_str,
            "workspace_id": str(query.workspace_id),
            "limit": query.top_k_coarse,
        })
        rows = result.fetchall()
        return [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                content_text=row.content_text,
                content_type="paragraph",
                section_path=row.section_path,
                page_numbers=row.page_numbers or [],
                score=float(row.score),
            )
            for row in rows
        ]

    async def _keyword_search(
        self,
        session: AsyncSession,
        query: RetrievalQuery,
    ) -> list[RetrievedChunk]:
        """PostgreSQL tsvector 全文検索。"""
        doc_filter = ""
        if query.document_ids:
            ids = ",".join(f"'{d!s}'" for d in query.document_ids)
            doc_filter = f"AND document_id IN ({ids})"

        sql = text(f"""
            SELECT id, document_id, content_text, section_path,
                   page_numbers,
                   ts_rank(
                       to_tsvector('english', content_text),
                       plainto_tsquery('english', :query)
                   ) AS score
            FROM paragraphs
            WHERE document_id IN (
                SELECT id FROM documents
                WHERE workspace_id = :workspace_id
            ) {doc_filter}
            AND to_tsvector('english', content_text)
                @@ plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :limit
        """)
        result = await session.execute(sql, {
            "query": query.query_text,
            "workspace_id": str(query.workspace_id),
            "limit": query.top_k_coarse,
        })
        rows = result.fetchall()
        return [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                content_text=row.content_text,
                content_type="paragraph",
                section_path=row.section_path,
                page_numbers=row.page_numbers or [],
                score=float(row.score),
            )
            for row in rows
        ]

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
            scores[chunk.chunk_id] = (
                scores.get(chunk.chunk_id, 0) + 1 / (k + rank + 1)
            )
            chunks[chunk.chunk_id] = chunk

        for rank, chunk in enumerate(list_b):
            scores[chunk.chunk_id] = (
                scores.get(chunk.chunk_id, 0) + 1 / (k + rank + 1)
            )
            chunks[chunk.chunk_id] = chunk

        sorted_ids = sorted(
            scores, key=lambda cid: scores[cid], reverse=True,
        )
        return [
            RetrievedChunk(
                chunk_id=cid,
                document_id=chunks[cid].document_id,
                content_text=chunks[cid].content_text,
                content_type=chunks[cid].content_type,
                section_path=chunks[cid].section_path,
                page_numbers=chunks[cid].page_numbers,
                score=scores[cid],
                metadata=chunks[cid].metadata,
            )
            for cid in sorted_ids
        ]
