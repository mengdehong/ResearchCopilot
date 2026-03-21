"""arxiv_search Skill 实现。

使用 arXiv Atom v1 REST API 检索学术论文，返回论文列表（标题、作者、摘要、URL）。
文档：https://info.arxiv.org/help/api/basics.html
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx

from backend.agent.skills.base import SkillDefinition
from backend.core.logger import get_logger

logger = get_logger(__name__)

_ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = "http://www.w3.org/2005/Atom"
_OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"


def _execute(
    query: str,
    max_results: int = 10,
    sort_by: str = "relevance",
) -> dict[str, Any]:
    """执行 arxiv 论文搜索。

    Args:
        query: 搜索关键词，支持 arxiv 高级搜索语法（ti:, au:, abs: 等）。
        max_results: 最多返回多少条结果（1-100）。
        sort_by: 排序方式，``relevance`` 或 ``submittedDate`` 或 ``lastUpdatedDate``。

    Returns:
        包含 ``papers`` 列表的字典。每篇论文包含 title、authors、abstract、url、published 字段。
    """
    params = {
        "search_query": query,
        "max_results": max(1, min(int(max_results), 100)),
        "sortBy": sort_by,
        "sortOrder": "descending",
    }
    logger.info("arxiv_search_start", query=query, max_results=params["max_results"])

    transport = httpx.HTTPTransport(retries=3)
    with httpx.Client(transport=transport, timeout=30.0) as client:
        response = client.get(_ARXIV_API_URL, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.text)

    papers: list[dict[str, Any]] = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        title_el = entry.find(f"{{{_ATOM_NS}}}title")
        abstract_el = entry.find(f"{{{_ATOM_NS}}}summary")
        published_el = entry.find(f"{{{_ATOM_NS}}}published")
        id_el = entry.find(f"{{{_ATOM_NS}}}id")

        authors = [
            author.findtext(f"{{{_ATOM_NS}}}name") or ""
            for author in entry.findall(f"{{{_ATOM_NS}}}author")
        ]

        title = (title_el.text or "").strip() if title_el is not None else ""
        abstract = (abstract_el.text or "").strip().replace("\n", " ") if abstract_el is not None else ""
        published_text = published_el.text if published_el is not None else None
        published = (published_text or "")[:10]
        url = (id_el.text or "").strip() if id_el is not None else ""

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
        })

    logger.info("arxiv_search_done", results=len(papers))
    return {"papers": papers}


ARXIV_SEARCH_SKILL = SkillDefinition(
    name="arxiv_search",
    description=(
        "Search for academic papers on arXiv by keyword or advanced query. "
        "Returns a list of papers with title, authors, abstract, URL, and publication date."
    ),
    input_schema={
        "query": "str — the search query (supports arxiv query syntax: ti:, au:, abs:, etc.)",
        "max_results": "int (optional, 1-100, default 10) — maximum number of results",
        "sort_by": "str (optional) — 'relevance' | 'submittedDate' | 'lastUpdatedDate'",
    },
    output_schema={
        "papers": "list[dict] — each item has: title, authors, abstract, url, published",
    },
    tags=["search", "academic", "arxiv", "literature"],
    execute=_execute,
)
