"""Agent Tools 测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.agent.tools.arxiv_tool import search_arxiv
from backend.agent.tools.sandbox_tool import execute_code
from backend.services.sandbox_manager import ExecutionResult


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

    @patch("backend.agent.tools.sandbox_tool._get_executor")
    def test_execute_code_calls_executor(self, mock_get_exec: MagicMock) -> None:
        """验证调用 DockerExecutor 并正确映射结果。"""
        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="hello\n",
            stderr="",
            output_files={"plot.png": b"..."},
            duration_seconds=1.5,
        )
        mock_executor = MagicMock()
        mock_executor.execute.return_value = mock_result
        mock_get_exec.return_value = mock_executor

        result = execute_code.invoke({"code": "print('hello')"})

        assert result["stdout"] == "hello\n"
        assert result["exit_code"] == 0
        assert result["artifacts"] == ["plot.png"]
        assert result["duration_ms"] == 1500
        mock_executor.execute.assert_called_once()

    @patch("backend.agent.tools.sandbox_tool._get_executor")
    def test_execute_code_propagates_failure(self, mock_get_exec: MagicMock) -> None:
        """验证执行失败时返回非零 exit_code。"""
        mock_result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="NameError: name 'x' is not defined",
            output_files={},
            duration_seconds=0.3,
        )
        mock_executor = MagicMock()
        mock_executor.execute.return_value = mock_result
        mock_get_exec.return_value = mock_executor

        result = execute_code.invoke({"code": "print(x)"})

        assert result["exit_code"] == 1
        assert "NameError" in result["stderr"]
        assert result["artifacts"] == []
