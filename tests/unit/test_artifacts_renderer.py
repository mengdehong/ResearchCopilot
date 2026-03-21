"""artifacts_renderer 单元测试。"""

from backend.services.artifacts_renderer import (
    render_artifacts,
    render_critique_artifacts,
    render_discovery_artifacts,
    render_execution_artifacts,
    render_extraction_artifacts,
    render_ideation_artifacts,
    render_publish_artifacts,
)


class TestRenderDiscovery:
    def test_basic_output(self) -> None:
        data = {
            "papers": [
                {
                    "arxiv_id": "2301.00001",
                    "title": "Test Paper",
                    "authors": ["Alice", "Bob"],
                    "year": 2023,
                    "abstract": "A test abstract.",
                    "relevance_comment": "Highly relevant.",
                }
            ],
            "selected_paper_ids": ["2301.00001"],
        }
        result = render_discovery_artifacts(data)
        assert "## 📚 文献发现结果" in result
        assert "Test Paper" in result
        assert "✅" in result
        assert "2301.00001" in result

    def test_empty_papers(self) -> None:
        result = render_discovery_artifacts({"papers": [], "selected_paper_ids": []})
        assert "## 📚 文献发现结果" in result


class TestRenderExtraction:
    def test_basic_output(self) -> None:
        data = {
            "reading_notes": [
                {
                    "paper_id": "2301.00001",
                    "key_contributions": ["Contribution A"],
                    "methodology": "Method X",
                    "experimental_setup": "Setup Y",
                    "main_results": "Result Z",
                    "limitations": ["Limit 1"],
                }
            ],
            "comparison_matrix": [
                {
                    "paper_id": "2301.00001",
                    "method": "Method X",
                    "dataset": "DS1",
                    "key_difference": "Faster",
                }
            ],
            "glossary": {"Term1": "Definition 1"},
        }
        result = render_extraction_artifacts(data)
        assert "## 📝 深度精读笔记" in result
        assert "Contribution A" in result
        assert "| 2301.00001" in result
        assert "**Term1**" in result


class TestRenderIdeation:
    def test_basic_output(self) -> None:
        data = {
            "research_gaps": [{"description": "Gap in coverage"}],
            "experiment_designs": [
                {
                    "hypothesis": "H1",
                    "method_description": "Do X",
                    "baselines": ["B1"],
                    "datasets": ["DS1"],
                    "evaluation_metrics": ["F1"],
                }
            ],
        }
        result = render_ideation_artifacts(data)
        assert "## 💡 研究构想" in result
        assert "Gap in coverage" in result
        assert "H1" in result


class TestRenderExecution:
    def test_basic_output(self) -> None:
        data = {
            "generated_code": "print('hello')",
            "execution_result": {"exit_code": 0, "stdout": "hello"},
        }
        result = render_execution_artifacts(data)
        assert "## ⚙️ 代码执行结果" in result
        assert "print('hello')" in result
        assert "✅ 成功" in result


class TestRenderCritique:
    def test_basic_output(self) -> None:
        data = {
            "extraction": {
                "verdict": "revise",
                "feedbacks": [
                    {
                        "severity": "major",
                        "category": "methodology",
                        "description": "Missing baseline",
                        "suggestion": "Add baseline comparison",
                    }
                ],
            }
        }
        result = render_critique_artifacts(data)
        assert "## 🔍 模拟审稿" in result
        assert "revise" in result
        assert "Missing baseline" in result


class TestRenderPublish:
    def test_uses_markdown_content(self) -> None:
        data = {"markdown": "# Report\n\nThis is a report."}
        result = render_publish_artifacts(data)
        assert result == "# Report\n\nThis is a report."

    def test_fallback_to_outline(self) -> None:
        data = {"outline": [{"title": "Section 1"}, {"title": "Section 2"}]}
        result = render_publish_artifacts(data)
        assert "Section 1" in result
        assert "Section 2" in result


class TestRenderArtifactsFacade:
    def test_known_workflow(self) -> None:
        data = {"markdown": "# Hello"}
        result = render_artifacts("publish", data)
        assert result == "# Hello"

    def test_unknown_workflow(self) -> None:
        result = render_artifacts("unknown_wf", {"data": "test"})
        assert result is None

    def test_empty_data(self) -> None:
        result = render_artifacts("discovery", {})
        assert result is None
