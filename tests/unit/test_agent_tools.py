"""Agent Tools 测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.agent.tools.arxiv_tool import search_arxiv
from backend.agent.tools.sandbox_tool import execute_code


class TestSearchArxiv:
    """ArXiv 搜索 Tool 测试。"""

    def test_search_arxiv_parses_xml(self) -> None:
        """验证 ArXiv API 响应解析。"""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>Test Paper Title</title>
    <summary>This is a test abstract.</summary>
    <published>2023-01-01T00:00:00Z</published>
    <author><name>Author One</name></author>
    <author><name>Author Two</name></author>
  </entry>
</feed>"""
        mock_response = MagicMock()
        mock_response.text = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("backend.agent.tools.arxiv_tool.httpx.get", return_value=mock_response):
            results = search_arxiv.invoke({"query": "test", "max_results": 5})

        assert len(results) == 1
        paper = results[0]
        assert paper["title"] == "Test Paper Title"
        assert paper["abstract"] == "This is a test abstract."
        assert paper["authors"] == ["Author One", "Author Two"]
        assert paper["year"] == 2023
        assert paper["source"] == "arxiv"
        assert "2301.00001" in paper["arxiv_id"]

    def test_search_arxiv_empty_results(self) -> None:
        """空结果返回空列表。"""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""
        mock_response = MagicMock()
        mock_response.text = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("backend.agent.tools.arxiv_tool.httpx.get", return_value=mock_response):
            results = search_arxiv.invoke({"query": "nonexistent"})

        assert results == []


class TestExecuteCode:
    """沙盒执行 Tool 测试。"""

    def test_execute_code_returns_result(self) -> None:
        """验证占位结果格式。"""
        result = execute_code.invoke({"code": "print('hello')"})
        assert "stdout" in result
        assert "stderr" in result
        assert "exit_code" in result
        assert result["exit_code"] == 0

    def test_execute_code_with_language(self) -> None:
        """验证带 language 参数。"""
        result = execute_code.invoke({"code": "console.log('hi')", "language": "javascript"})
        assert result["exit_code"] == 0
