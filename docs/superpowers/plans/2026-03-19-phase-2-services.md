# Phase 2: 服务层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 4 个核心服务层组件（LLM Gateway、Sandbox Manager、Parser Engine、RAG Engine），为 Agent 层和 BFF 层提供基础能力。

**Architecture:** 所有服务在 `backend/services/` 下，使用 Protocol 抽象接口，具体实现通过依赖注入替换。服务层为纯业务逻辑，无框架依赖。

**Tech Stack:** LangChain Core / Docker SDK / MinerU / pgvector / sentence-transformers

**前置条件：** Phase 1 全部完成（config、database、ORM models、Alembic）

**对应设计文档：**
- [沙箱设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-sandbox-design.md) — §三 数据模型, §四 容器生命周期
- [RAG Pipeline 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-rag-pipeline-design.md) — §四 Retrieval Pipeline
- [Agent 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-langgraph-agent-design.md) — §一 State 架构（ExecutionResult 等数据模型）
- [可观测性设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-observability-design.md) — §二 日志规范, §三.2 LangSmith 集成

---

## 文件结构

```
backend/
├── services/
│   ├── __init__.py
│   ├── llm_gateway.py         # [NEW] LLM 统一封装（多 Provider 适配、限流降级）
│   ├── sandbox_manager.py     # [NEW] CodeExecutor Protocol + DockerExecutor 实现
│   ├── parser_engine.py       # [NEW] MinerU PDF 解析封装
│   └── rag_engine.py          # [NEW] 切块、Embedding、向量检索、Rerank
│
tests/
├── unit/
│   ├── test_llm_gateway.py    # [NEW]
│   ├── test_sandbox_manager.py# [NEW]（mock Docker）
│   └── test_rag_engine.py     # [NEW]（mock DB）
└── integration/
    └── test_sandbox.py        # [NEW]（需要 Docker Daemon）
```

---

## Task 1: LLM Gateway — llm_gateway.py

**Files:**
- Create: `backend/services/llm_gateway.py`
- Test: `tests/unit/test_llm_gateway.py`

> 设计要点：统一封装多 Provider（OpenAI、Anthropic、Google），上层不感知 SDK 差异。使用 langchain-core 的 `BaseChatModel` 作统一接口。

- [ ] **Step 1: 编写测试**

`tests/unit/test_llm_gateway.py`:
```python
"""LLM Gateway 测试。"""
import pytest
from unittest.mock import MagicMock, patch

from backend.services.llm_gateway import LLMGateway, LLMProvider


def test_get_model_openai() -> None:
    """验证 OpenAI provider 创建正确的模型实例。"""
    gateway = LLMGateway(
        openai_api_key="sk-test",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )
    model = gateway.get_model()
    assert model is not None


def test_get_model_with_override() -> None:
    """验证可以覆盖 provider 和 model。"""
    gateway = LLMGateway(
        openai_api_key="sk-test",
        anthropic_api_key="sk-ant-test",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )
    model = gateway.get_model(provider=LLMProvider.ANTHROPIC, model="claude-3-5-sonnet-20241022")
    assert model is not None


def test_get_model_missing_key_raises() -> None:
    """未配置 API Key 时应抛错。"""
    gateway = LLMGateway(
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )
    with pytest.raises(ValueError, match="API key not configured"):
        gateway.get_model()
```

- [ ] **Step 2: 实现 llm_gateway.py**

`backend/services/llm_gateway.py`:
```python
"""LLM 统一封装。多 Provider 适配，上层只依赖 langchain-core 的 BaseChatModel。"""
from enum import StrEnum

from langchain_core.language_models import BaseChatModel


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMGateway:
    """LLM 统一网关。根据 provider 返回对应的 ChatModel 实例。"""

    def __init__(
        self,
        *,
        default_provider: LLMProvider,
        default_model: str,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        google_api_key: str | None = None,
    ) -> None:
        self._default_provider = default_provider
        self._default_model = default_model
        self._keys: dict[LLMProvider, str | None] = {
            LLMProvider.OPENAI: openai_api_key,
            LLMProvider.ANTHROPIC: anthropic_api_key,
            LLMProvider.GOOGLE: google_api_key,
        }

    def get_model(
        self,
        *,
        provider: LLMProvider | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseChatModel:
        """获取 LLM 实例。可覆盖默认 provider 和 model。"""
        provider = provider or self._default_provider
        model = model or self._default_model
        api_key = self._keys.get(provider)

        if not api_key:
            raise ValueError(f"API key not configured for provider: {provider}")

        return self._create_model(provider, model, api_key, temperature)

    def _create_model(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float,
    ) -> BaseChatModel:
        """工厂方法：根据 provider 创建对应的 ChatModel。"""
        match provider:
            case LLMProvider.OPENAI:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(model=model, api_key=api_key, temperature=temperature)
            case LLMProvider.ANTHROPIC:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(model=model, api_key=api_key, temperature=temperature)
            case LLMProvider.GOOGLE:
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=model, google_api_key=api_key, temperature=temperature,
                )
            case _:
                raise ValueError(f"Unsupported provider: {provider}")
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/unit/test_llm_gateway.py -v
```
Expected: `3 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/services/llm_gateway.py tests/unit/test_llm_gateway.py
git commit -m "feat: add LLM Gateway with multi-provider support"
```

---

## Task 2: Sandbox Manager — sandbox_manager.py

**Files:**
- Create: `backend/services/sandbox_manager.py`
- Create: `deployment/sandbox_image/Dockerfile`
- Test: `tests/unit/test_sandbox_manager.py`
- Test: `tests/integration/test_sandbox.py`

> 设计要点：Protocol 抽象接口 `CodeExecutor`，`DockerExecutor` 实现容器生命周期（创建→注入→执行→提取→销毁）。对应 [沙箱设计 spec](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-sandbox-design.md)。

- [ ] **Step 1: 创建 Sandbox Dockerfile**

`deployment/sandbox_image/Dockerfile`:
```dockerfile
FROM python:3.11-slim

RUN useradd -m -s /bin/bash sandbox

RUN pip install --no-cache-dir \
    numpy pandas scipy matplotlib seaborn \
    scikit-learn statsmodels networkx sympy

RUN mkdir /workspace /output && \
    chown sandbox:sandbox /workspace /output

USER sandbox
WORKDIR /workspace
```

构建命令：
```bash
docker build -t research-copilot-sandbox:latest deployment/sandbox_image/
```

- [ ] **Step 2: 实现 sandbox_manager.py**

`backend/services/sandbox_manager.py`:
```python
"""容器化沙箱管理。CodeExecutor Protocol + DockerExecutor 实现。"""
import io
import tarfile
import time
from dataclasses import dataclass, field
from typing import Protocol

import docker
from docker.models.containers import Container

from backend.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExecutionRequest:
    """沙箱执行请求。"""
    code: str
    timeout_seconds: int = 600
    input_files: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    """沙箱执行结果。"""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    output_files: dict[str, bytes] = field(default_factory=dict)
    duration_seconds: float = 0.0


class CodeExecutor(Protocol):
    """代码执行器抽象接口。"""
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


class DockerExecutor:
    """基于 Docker 的代码执行器。"""

    LABELS = {"app": "research-copilot", "role": "sandbox"}

    def __init__(
        self,
        *,
        image: str = "research-copilot-sandbox:latest",
        memory_limit: str = "4g",
        cpu_count: int = 2,
    ) -> None:
        self._image = image
        self._memory_limit = memory_limit
        self._nano_cpus = cpu_count * 1_000_000_000
        self._client = docker.from_env()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """创建容器→注入代码→执行→提取结果→强制销毁。"""
        container: Container | None = None
        start_time = time.monotonic()

        try:
            container = self._create_container()
            self._inject_code(container, request.code, request.input_files)
            exit_code, stdout, stderr = self._run(container, request.timeout_seconds)
            output_files = self._extract_outputs(container) if exit_code == 0 else {}
            duration = time.monotonic() - start_time

            return ExecutionResult(
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                output_files=output_files,
                duration_seconds=duration,
            )
        except docker.errors.DockerException as exc:
            logger.error("sandbox_execution_failed", error=str(exc))
            raise
        finally:
            if container:
                self._destroy_container(container)

    def _create_container(self) -> Container:
        return self._client.containers.create(
            image=self._image,
            network_disabled=True,
            mem_limit=self._memory_limit,
            nano_cpus=self._nano_cpus,
            user="sandbox",
            labels=self.LABELS,
            stdin_open=False,
            tty=False,
        )

    def _inject_code(
        self, container: Container, code: str, input_files: dict[str, bytes],
    ) -> None:
        tar_buffer = self._build_tar({"script.py": code.encode(), **{
            f"data/{name}": content for name, content in input_files.items()
        }})
        container.put_archive("/workspace/", tar_buffer)

    def _run(self, container: Container, timeout: int) -> tuple[int, str, str]:
        container.start()
        exit_code, output = container.exec_run(
            "python /workspace/script.py", demux=True,
        )
        stdout = (output[0] or b"").decode(errors="replace")
        stderr = (output[1] or b"").decode(errors="replace")
        return exit_code, stdout, stderr

    def _extract_outputs(self, container: Container) -> dict[str, bytes]:
        try:
            bits, _ = container.get_archive("/output/")
            tar_stream = io.BytesIO(b"".join(bits))
            result: dict[str, bytes] = {}
            with tarfile.open(fileobj=tar_stream) as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            name = member.name.split("/", 1)[-1] if "/" in member.name else member.name
                            result[name] = f.read()
            return result
        except docker.errors.NotFound:
            return {}

    def _destroy_container(self, container: Container) -> None:
        try:
            container.stop(timeout=5)
            container.remove(force=True)
        except docker.errors.DockerException:
            logger.warning("sandbox_cleanup_failed", container_id=container.short_id)

    @staticmethod
    def _build_tar(files: dict[str, bytes]) -> bytes:
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            for name, content in files.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        tar_buffer.seek(0)
        return tar_buffer.read()
```

- [ ] **Step 3: 编写单元测试（mock Docker）**

`tests/unit/test_sandbox_manager.py`:
```python
"""Sandbox Manager 单元测试（mock Docker SDK）。"""
from unittest.mock import MagicMock, patch
from backend.services.sandbox_manager import DockerExecutor, ExecutionRequest, ExecutionResult


@patch("backend.services.sandbox_manager.docker")
def test_execute_success(mock_docker) -> None:
    container = MagicMock()
    container.exec_run.return_value = (0, (b"result\n", b""))
    container.get_archive.return_value = (iter([b""]), None)
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="print('hello')"))

    assert result.success is True
    assert result.exit_code == 0
    container.start.assert_called_once()
    container.remove.assert_called_once()


@patch("backend.services.sandbox_manager.docker")
def test_execute_failure(mock_docker) -> None:
    container = MagicMock()
    container.exec_run.return_value = (1, (b"", b"SyntaxError\n"))
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="invalid python"))

    assert result.success is False
    assert "SyntaxError" in result.stderr
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/unit/test_sandbox_manager.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/sandbox_manager.py deployment/sandbox_image/Dockerfile \
       tests/unit/test_sandbox_manager.py
git commit -m "feat: add DockerExecutor sandbox manager with CodeExecutor protocol"
```

---

## Task 3: Parser Engine — parser_engine.py

**Files:**
- Create: `backend/services/parser_engine.py`

> 设计要点：封装 MinerU PDF 解析，输出 `ParsedDocument` 结构化对象。MVP 阶段提供 fallback（PyMuPDF 纯文本提取）。由 Celery Worker 调用，非实时。

- [ ] **Step 1: 实现 parser_engine.py**

`backend/services/parser_engine.py`:
```python
"""PDF 解析引擎。封装 MinerU 和 PyMuPDF fallback。"""
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from backend.core.logger import get_logger

logger = get_logger(__name__)


class ParseQuality(StrEnum):
    FULL = "full"
    DEGRADED = "degraded"


@dataclass
class ParsedSection:
    """解析出的章节。"""
    heading: str
    level: int
    content: str
    page_numbers: list[int] = field(default_factory=list)


@dataclass
class ParsedTable:
    """解析出的表格。"""
    title: str
    raw_data: dict
    page_number: int
    section_path: str = ""


@dataclass
class ParsedFigure:
    """解析出的图表。"""
    caption: str
    image_path: str
    context: str
    page_number: int
    section_path: str = ""


@dataclass
class ParsedEquation:
    """解析出的公式。"""
    latex: str
    context: str
    label: str | None = None
    page_number: int = 0
    section_path: str = ""


@dataclass
class ParsedDocument:
    """完整的解析结果。"""
    title: str
    abstract: str
    sections: list[ParsedSection] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    figures: list[ParsedFigure] = field(default_factory=list)
    equations: list[ParsedEquation] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    quality: ParseQuality = ParseQuality.FULL


class PdfParser(Protocol):
    """PDF 解析器抽象接口。"""
    def parse(self, pdf_path: Path) -> ParsedDocument: ...


class MinerUParser:
    """MinerU GPU 解析器。"""

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """调用 MinerU 解析 PDF 为结构化文档。"""
        logger.info("mineru_parse_start", path=str(pdf_path))
        try:
            # MinerU API 调用（实际集成时填充）
            # from magic_pdf.pipe.UNIPipe import UNIPipe
            raise NotImplementedError("MinerU integration pending")
        except Exception:
            logger.warning("mineru_parse_failed_fallback", path=str(pdf_path))
            return FallbackParser().parse(pdf_path)


class FallbackParser:
    """PyMuPDF 纯文本 fallback 解析器。"""

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """降级解析：仅提取纯文本。"""
        logger.info("fallback_parse_start", path=str(pdf_path))
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        text_parts: list[str] = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()

        full_text = "\n".join(text_parts)
        return ParsedDocument(
            title=pdf_path.stem,
            abstract="",
            sections=[ParsedSection(heading="Full Text", level=1, content=full_text)],
            quality=ParseQuality.DEGRADED,
        )
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/parser_engine.py
git commit -m "feat: add PDF parser engine with MinerU and PyMuPDF fallback"
```

---

## Task 4: RAG Engine — rag_engine.py

**Files:**
- Create: `backend/services/rag_engine.py`
- Test: `tests/unit/test_rag_engine.py`

> 设计要点：封装 Embedding 生成、向量+关键词混合检索、RRF 融合、Reranker 精排。对应 [RAG Pipeline 设计 spec §四](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-rag-pipeline-design.md)。

- [ ] **Step 1: 实现 rag_engine.py**

`backend/services/rag_engine.py`:
```python
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
    metadata: dict = field(default_factory=dict)


class RAGEngine:
    """RAG 检索引擎。"""

    def __init__(self, *, embedding_model_name: str = "BAAI/bge-m3") -> None:
        self._embedding_model_name = embedding_model_name
        self._embedder: object | None = None

    def _get_embedder(self):
        """延迟加载 Embedding 模型。"""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self._embedding_model_name)
        return self._embedder

    def embed_text(self, text: str) -> list[float]:
        """生成文本向量。"""
        embedder = self._get_embedder()
        return embedder.encode(text).tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。"""
        embedder = self._get_embedder()
        return embedder.encode(texts).tolist()

    async def retrieve(
        self,
        query: RetrievalQuery,
        session: AsyncSession,
    ) -> list[RetrievedChunk]:
        """混合检索：向量 + 关键词 → RRF 融合 → 返回 top-N。"""
        query_embedding = self.embed_text(query.query_text)

        # 并行执行向量检索和关键词检索
        vector_results = await self._vector_search(
            session, query, query_embedding,
        )
        keyword_results = await self._keyword_search(
            session, query,
        )

        # RRF 融合
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
            ids = ",".join(f"'{str(d)}'" for d in query.document_ids)
            doc_filter = f"AND document_id IN ({ids})"

        sql = text(f"""
            SELECT id, document_id, content_text, section_path,
                   page_numbers, 1 - (embedding <=> :embedding) AS score
            FROM paragraphs
            WHERE document_id IN (
                SELECT id FROM documents WHERE workspace_id = :workspace_id
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
                chunk_id=row.id, document_id=row.document_id,
                content_text=row.content_text, content_type="paragraph",
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
        """PostgreSQL tsvector 全文检索。"""
        sql = text("""
            SELECT id, document_id, content_text, section_path,
                   page_numbers, ts_rank(tsv, plainto_tsquery(:query)) AS score
            FROM paragraphs
            WHERE document_id IN (
                SELECT id FROM documents WHERE workspace_id = :workspace_id
            )
            AND tsv @@ plainto_tsquery(:query)
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
                chunk_id=row.id, document_id=row.document_id,
                content_text=row.content_text, content_type="paragraph",
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
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (k + rank + 1)
            chunks[chunk.chunk_id] = chunk

        for rank, chunk in enumerate(list_b):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (k + rank + 1)
            chunks[chunk.chunk_id] = chunk

        sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
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
```

- [ ] **Step 2: 编写 RRF 融合单元测试**

`tests/unit/test_rag_engine.py`:
```python
"""RAG Engine 单元测试。"""
import uuid
from backend.services.rag_engine import RAGEngine, RetrievedChunk


def _make_chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.UUID(chunk_id),
        document_id=uuid.uuid4(),
        content_text="test",
        content_type="paragraph",
        section_path="1. Intro",
        page_numbers=[1],
        score=score,
    )


ID_A = "00000000-0000-0000-0000-000000000001"
ID_B = "00000000-0000-0000-0000-000000000002"
ID_C = "00000000-0000-0000-0000-000000000003"


def test_rrf_merge_basic() -> None:
    list_a = [_make_chunk(ID_A, 0.9), _make_chunk(ID_B, 0.8)]
    list_b = [_make_chunk(ID_B, 0.85), _make_chunk(ID_C, 0.7)]

    merged = RAGEngine._rrf_merge(list_a, list_b)
    ids = [str(c.chunk_id) for c in merged]

    # B 出现在两个列表中，RRF 分数应最高
    assert ids[0] == ID_B
    assert len(merged) == 3


def test_rrf_merge_empty() -> None:
    merged = RAGEngine._rrf_merge([], [])
    assert merged == []
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/unit/test_rag_engine.py -v
```
Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/services/rag_engine.py tests/unit/test_rag_engine.py
git commit -m "feat: add RAG engine with hybrid retrieval and RRF fusion"
```

## Task 5: 可观测性增强

**Files:**
- Modify: `backend/core/logger.py`
- Modify: `backend/core/config.py`

> 对应 [可观测性设计 §二.3 + §三.2](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-observability-design.md)。

- [ ] **Step 1: logger.py 追加敏感字段脱敏 processor**

在 `shared_processors` 列表中追加 `sanitize_sensitive_fields` processor，对字段名包含 `api_key`, `secret`, `token`, `password`, `jwt`, `authorization`（不区分大小写）的值替换为 `***`。

- [ ] **Step 2: config.py 追加 LangSmith 配置**

`Settings` 类追加：
```python
# --- LangSmith ---
langsmith_api_key: str | None = None
```

- [ ] **Step 3: 在 4 个 Service 中添加业务关键日志点**

按可观测性设计 §2.4 表格，在已实现的 `llm_gateway.py`、`sandbox_manager.py`、`parser_engine.py`、`rag_engine.py` 中确保 INFO 级别日志包含规定的结构化字段。

- [ ] **Step 4: .env.example 追加 LangSmith 变量**

```
# --- LangSmith ---
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGSMITH_API_KEY=
```

- [ ] **Step 5: Commit**

```bash
git add backend/core/logger.py backend/core/config.py .env.example
git commit -m "feat: add log sanitization processor and LangSmith config"
```

---

## 验证清单

| 检查项          | 命令                                                  | 期望结果 |
| --------------- | ----------------------------------------------------- | -------- |
| LLM Gateway     | `uv run pytest tests/unit/test_llm_gateway.py -v`     | 3 passed |
| Sandbox Manager | `uv run pytest tests/unit/test_sandbox_manager.py -v` | 2 passed |
| RAG Engine      | `uv run pytest tests/unit/test_rag_engine.py -v`      | 2 passed |
| 全量 lint       | `uv run ruff check backend/services/ tests/`          | 0 errors |
| 全量测试        | `uv run pytest tests/unit/ -v`                        | 全部通过 |

---

**Phase 2 完成标志：** 全部单元测试通过 + lint 无报错 + 4 个服务文件实现完毕 → 可进入 Phase 3。
