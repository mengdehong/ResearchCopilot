"""ArXiv 论文搜索 Tool — 使用 httpx 调用 ArXiv API。"""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import tool

from backend.core.logger import get_logger

logger = get_logger(__name__)

_ARXIV_API_URL = "https://export.arxiv.org/api/query"
_MAX_RESULTS = 10


@tool
def search_arxiv(query: str, max_results: int = _MAX_RESULTS) -> list[dict[str, Any]]:
    """Search ArXiv for academic papers matching the query.

    Args:
        query: Search query string (supports ArXiv search syntax).
        max_results: Maximum number of results to return (default 10).

    Returns:
        List of paper metadata dictionaries.
    """
    import xml.etree.ElementTree as ET

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        response = httpx.get(_ARXIV_API_URL, params=params, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("arxiv_search_failed", query=query, error=str(e))
        raise

    # 解析 Atom XML
    root = ET.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    papers: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        id_el = entry.find("atom:id", ns)
        published_el = entry.find("atom:published", ns)

        # 提取作者列表
        authors = [
            a.find("atom:name", ns).text  # type: ignore[union-attr]
            for a in entry.findall("atom:author", ns)
            if a.find("atom:name", ns) is not None
        ]

        arxiv_id = ""
        if id_el is not None and id_el.text:
            arxiv_id = id_el.text.split("/abs/")[-1]

        year = 0
        if published_el is not None and published_el.text:
            year = int(published_el.text[:4])

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": (title_el.text or "").strip().replace("\n", " "),
                "abstract": (summary_el.text or "").strip().replace("\n", " ")
                if summary_el is not None
                else "",
                "authors": authors,
                "year": year,
                "source": "arxiv",
            }
        )

    logger.info("arxiv_search_done", query=query, result_count=len(papers))
    return papers
