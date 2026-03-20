"""文档解析任务单元测试。四阶段管道: 解析→分类→LLM增强→Embedding入库。"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.parser_engine import (
    ParsedDocument,
    ParsedSection,
    ParsedTable,
    ParseQuality,
)


DOC_ID = uuid.uuid4()


def _make_parsed_doc() -> ParsedDocument:
    return ParsedDocument(
        title="Test Paper",
        abstract="This is a test abstract.",
        sections=[
            ParsedSection(
                heading="1. Introduction",
                level=1,
                content="We introduce the method.",
                page_numbers=[1],
            ),
        ],
        tables=[
            ParsedTable(
                title="Table 1",
                raw_data={"rows": [["a", "b"]]},
                page_number=3,
                section_path="Results",
            ),
        ],
    )


@pytest.mark.asyncio
async def test_parse_document_status_flow_completed() -> None:
    """成功时状态应从 pending → parsing → completed。"""
    from backend.workers.tasks.parse_document import run_parse_pipeline

    status_updates: list[tuple[uuid.UUID, str]] = []

    async def fake_update_status(doc_id: uuid.UUID, status: str) -> None:
        status_updates.append((doc_id, status))

    async def fake_get_file_path(doc_id: uuid.UUID) -> str:
        return "/tmp/test.pdf"

    mock_parser = MagicMock()
    mock_parser.parse.return_value = _make_parsed_doc()

    mock_rag = MagicMock()
    mock_rag.embed_texts.side_effect = lambda texts: [[0.1] * 1024] * len(texts)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    await run_parse_pipeline(
        doc_id=DOC_ID,
        update_status=fake_update_status,
        get_file_path=fake_get_file_path,
        parser=mock_parser,
        rag_engine=mock_rag,
        session=mock_session,
    )

    statuses = [s[1] for s in status_updates]
    assert statuses[0] == "parsing"
    assert statuses[-1] == "completed"


@pytest.mark.asyncio
async def test_parse_document_status_flow_failed() -> None:
    """解析失败时状态应回写 failed。"""
    from backend.workers.tasks.parse_document import run_parse_pipeline

    status_updates: list[tuple[uuid.UUID, str]] = []

    async def fake_update_status(doc_id: uuid.UUID, status: str) -> None:
        status_updates.append((doc_id, status))

    async def fake_get_file_path(doc_id: uuid.UUID) -> str:
        return "/tmp/test.pdf"

    mock_parser = MagicMock()
    mock_parser.parse.side_effect = RuntimeError("MinerU unavailable")

    mock_rag = MagicMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # 同时提供 fallback_parser 也失败的情况
    mock_fallback = MagicMock()
    mock_fallback.parse.side_effect = RuntimeError("PyMuPDF also failed")

    with pytest.raises(RuntimeError):
        await run_parse_pipeline(
            doc_id=DOC_ID,
            update_status=fake_update_status,
            get_file_path=fake_get_file_path,
            parser=mock_parser,
            rag_engine=mock_rag,
            session=mock_session,
            fallback_parser=mock_fallback,
        )

    statuses = [s[1] for s in status_updates]
    assert "parsing" in statuses
    assert statuses[-1] == "failed"


@pytest.mark.asyncio
async def test_parse_document_fallback_on_primary_failure() -> None:
    """主解析器失败时应使用 fallback parser, 质量标记为 degraded。"""
    from backend.workers.tasks.parse_document import run_parse_pipeline

    fallback_doc = _make_parsed_doc()
    fallback_doc = ParsedDocument(
        title=fallback_doc.title,
        abstract=fallback_doc.abstract,
        sections=fallback_doc.sections,
        quality=ParseQuality.DEGRADED,
    )

    status_updates: list[tuple[uuid.UUID, str]] = []

    async def fake_update_status(doc_id: uuid.UUID, status: str) -> None:
        status_updates.append((doc_id, status))

    async def fake_get_file_path(doc_id: uuid.UUID) -> str:
        return "/tmp/test.pdf"

    mock_parser = MagicMock()
    mock_parser.parse.side_effect = RuntimeError("MinerU unavailable")

    mock_fallback = MagicMock()
    mock_fallback.parse.return_value = fallback_doc

    mock_rag = MagicMock()
    mock_rag.embed_texts.side_effect = lambda texts: [[0.1] * 1024] * len(texts)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    await run_parse_pipeline(
        doc_id=DOC_ID,
        update_status=fake_update_status,
        get_file_path=fake_get_file_path,
        parser=mock_parser,
        rag_engine=mock_rag,
        session=mock_session,
        fallback_parser=mock_fallback,
    )

    statuses = [s[1] for s in status_updates]
    assert statuses[-1] == "completed"
    mock_fallback.parse.assert_called_once()


@pytest.mark.asyncio
async def test_parse_document_llm_failure_does_not_block() -> None:
    """LLM 增强失败时不应阻塞管道, 最终仍为 completed。"""
    from backend.workers.tasks.parse_document import run_parse_pipeline

    status_updates: list[tuple[uuid.UUID, str]] = []

    async def fake_update_status(doc_id: uuid.UUID, status: str) -> None:
        status_updates.append((doc_id, status))

    async def fake_get_file_path(doc_id: uuid.UUID) -> str:
        return "/tmp/test.pdf"

    mock_parser = MagicMock()
    mock_parser.parse.return_value = _make_parsed_doc()

    mock_rag = MagicMock()
    mock_rag.embed_texts.side_effect = lambda texts: [[0.1] * 1024] * len(texts)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # LLM enhancer 抛异常
    mock_llm_enhancer = AsyncMock(side_effect=RuntimeError("LLM down"))

    await run_parse_pipeline(
        doc_id=DOC_ID,
        update_status=fake_update_status,
        get_file_path=fake_get_file_path,
        parser=mock_parser,
        rag_engine=mock_rag,
        session=mock_session,
        llm_enhancer=mock_llm_enhancer,
    )

    statuses = [s[1] for s in status_updates]
    assert statuses[-1] == "completed"


@pytest.mark.asyncio
async def test_parse_document_calls_embed_texts() -> None:
    """Stage 4 应调用 rag_engine.embed_texts 为所有文本内容生成向量。"""
    from backend.workers.tasks.parse_document import run_parse_pipeline

    async def fake_update_status(doc_id: uuid.UUID, status: str) -> None:
        pass

    async def fake_get_file_path(doc_id: uuid.UUID) -> str:
        return "/tmp/test.pdf"

    mock_parser = MagicMock()
    mock_parser.parse.return_value = _make_parsed_doc()

    mock_rag = MagicMock()
    mock_rag.embed_texts.side_effect = lambda texts: [[0.1] * 1024] * len(texts)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    await run_parse_pipeline(
        doc_id=DOC_ID,
        update_status=fake_update_status,
        get_file_path=fake_get_file_path,
        parser=mock_parser,
        rag_engine=mock_rag,
        session=mock_session,
    )

    mock_rag.embed_texts.assert_called_once()
    texts = mock_rag.embed_texts.call_args[0][0]
    assert len(texts) > 0  # 至少有 abstract + intro paragraph
