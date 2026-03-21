"""Artifacts → Markdown 渲染器。将各 WF 的结构化 artifacts dict 转为人类可读 Markdown。"""

from __future__ import annotations

from collections.abc import Callable

from backend.core.logger import get_logger

logger = get_logger(__name__)


def render_discovery_artifacts(data: dict) -> str:
    """Discovery WF artifacts → Markdown。"""
    lines: list[str] = ["## 📚 文献发现结果\n"]

    papers = data.get("papers", [])
    selected_ids = data.get("selected_paper_ids", [])

    if selected_ids:
        lines.append(f"已筛选 **{len(selected_ids)}** 篇论文（共检索 {len(papers)} 篇）\n")

    for paper in papers:
        arxiv_id = paper.get("arxiv_id", "")
        is_selected = arxiv_id in selected_ids
        marker = "✅" if is_selected else "📄"
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", [])
        year = paper.get("year", "")
        abstract = paper.get("abstract", "")
        relevance = paper.get("relevance_comment", "")

        lines.append(f"### {marker} {title}\n")
        if authors:
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."
            lines.append(f"**Authors:** {author_str}  ")
        if year:
            lines.append(f"**Year:** {year}  ")
        if arxiv_id:
            lines.append(f"**arXiv:** {arxiv_id}  ")
        lines.append("")
        if abstract:
            lines.append(f"> {abstract[:300]}{'...' if len(abstract) > 300 else ''}\n")
        if relevance:
            lines.append(f"*{relevance}*\n")

    return "\n".join(lines)


def render_extraction_artifacts(data: dict) -> str:
    """Extraction WF artifacts → Markdown。"""
    lines: list[str] = ["## 📝 深度精读笔记\n"]

    notes = data.get("reading_notes", [])
    for note in notes:
        paper_id = note.get("paper_id", "Unknown")
        lines.append(f"### 📖 {paper_id}\n")

        contributions = note.get("key_contributions", [])
        if contributions:
            lines.append("**核心贡献:**")
            for c in contributions:
                lines.append(f"- {c}")
            lines.append("")

        methodology = note.get("methodology", "")
        if methodology:
            lines.append(f"**方法论:** {methodology}\n")

        setup = note.get("experimental_setup", "")
        if setup:
            lines.append(f"**实验设置:** {setup}\n")

        results = note.get("main_results", "")
        if results:
            lines.append(f"**主要结果:** {results}\n")

        limitations = note.get("limitations", [])
        if limitations:
            lines.append("**局限性:**")
            for lim in limitations:
                lines.append(f"- {lim}")
            lines.append("")

    # 对比矩阵
    matrix = data.get("comparison_matrix", [])
    if matrix:
        lines.append("### 📊 跨文档对比\n")
        lines.append("| Paper | Method | Dataset | Key Difference |")
        lines.append("|-------|--------|---------|----------------|")
        for entry in matrix:
            paper_id = entry.get("paper_id", "")
            method = entry.get("method", "")
            dataset = entry.get("dataset", "")
            diff = entry.get("key_difference", "")
            lines.append(f"| {paper_id} | {method} | {dataset} | {diff} |")
        lines.append("")

    # 术语表
    glossary = data.get("glossary", {})
    if glossary:
        lines.append("### 📖 术语表\n")
        for term, definition in glossary.items():
            lines.append(f"- **{term}**: {definition}")
        lines.append("")

    return "\n".join(lines)


def render_ideation_artifacts(data: dict) -> str:
    """Ideation WF artifacts → Markdown。"""
    lines: list[str] = ["## 💡 研究构想\n"]

    gaps = data.get("research_gaps", [])
    if gaps:
        lines.append("### 研究空白\n")
        for i, gap in enumerate(gaps, 1):
            desc = gap.get("description", "") if isinstance(gap, dict) else str(gap)
            lines.append(f"{i}. {desc}")
        lines.append("")

    designs = data.get("experiment_designs", [])
    if designs:
        lines.append("### 实验方案\n")
        for i, design in enumerate(designs, 1):
            if isinstance(design, dict):
                hypothesis = design.get("hypothesis", "")
                method = design.get("method_description", "")
                lines.append(f"#### 方案 {i}: {hypothesis}\n")
                if method:
                    lines.append(f"{method}\n")
                baselines = design.get("baselines", [])
                if baselines:
                    lines.append(f"**Baselines:** {', '.join(baselines)}  ")
                datasets = design.get("datasets", [])
                if datasets:
                    lines.append(f"**Datasets:** {', '.join(datasets)}  ")
                metrics = design.get("evaluation_metrics", [])
                if metrics:
                    lines.append(f"**Metrics:** {', '.join(metrics)}\n")
            else:
                lines.append(f"{i}. {design}")
        lines.append("")

    return "\n".join(lines)


def render_execution_artifacts(data: dict) -> str:
    """Execution WF artifacts → Markdown。"""
    lines: list[str] = ["## ⚙️ 代码执行结果\n"]

    code = data.get("generated_code", "")
    if code:
        lines.append("### 生成代码\n")
        lines.append("```python")
        lines.append(code)
        lines.append("```\n")

    result = data.get("execution_result", {})
    if isinstance(result, dict):
        exit_code = result.get("exit_code")
        if exit_code is not None:
            status = "✅ 成功" if exit_code == 0 else f"❌ 失败 (exit code: {exit_code})"
            lines.append(f"**执行状态:** {status}\n")
        stdout = result.get("stdout", "")
        if stdout:
            lines.append("### 标准输出\n")
            lines.append("```")
            lines.append(stdout[:2000])
            lines.append("```\n")

    return "\n".join(lines)


def render_critique_artifacts(data: dict) -> str:
    """Critique WF artifacts → Markdown。"""
    lines: list[str] = ["## 🔍 模拟审稿\n"]

    for target_wf, result in data.items():
        if not isinstance(result, dict):
            continue
        verdict = result.get("verdict", "")
        lines.append(f"### 审查目标: {target_wf}\n")
        lines.append(f"**裁决:** {verdict}\n")

        feedbacks = result.get("feedbacks", [])
        if feedbacks:
            for fb in feedbacks:
                severity = fb.get("severity", "")
                category = fb.get("category", "")
                description = fb.get("description", "")
                suggestion = fb.get("suggestion", "")
                lines.append(f"- **[{severity}] {category}**: {description}")
                if suggestion:
                    lines.append(f"  - 建议: {suggestion}")
            lines.append("")

    return "\n".join(lines)


def render_publish_artifacts(data: dict) -> str:
    """Publish WF artifacts → Markdown。直接返回 markdown_content。"""
    markdown = data.get("markdown", "")
    if markdown:
        return markdown

    # Fallback: 从 outline 构建
    outline = data.get("outline", [])
    if outline:
        lines = ["## 📄 研究报告\n"]
        for section in outline:
            title = section.get("title", "") if isinstance(section, dict) else str(section)
            lines.append(f"### {title}\n")
        return "\n".join(lines)

    return ""


_RENDERERS: dict[str, Callable[[dict], str]] = {
    "discovery": render_discovery_artifacts,
    "extraction": render_extraction_artifacts,
    "ideation": render_ideation_artifacts,
    "execution": render_execution_artifacts,
    "critique": render_critique_artifacts,
    "publish": render_publish_artifacts,
}


def render_artifacts(workflow: str, data: dict) -> str | None:
    """将指定 WF 的 artifacts dict 渲染为 Markdown。

    Args:
        workflow: WF 名称，如 "discovery"、"extraction" 等。
        data: 该 WF 命名空间下的 artifacts dict。

    Returns:
        Markdown 字符串，或 None（无对应渲染器或数据为空）。
    """
    renderer = _RENDERERS.get(workflow)
    if renderer is None:
        logger.warning("artifacts_renderer_no_handler", workflow=workflow)
        return None

    if not data:
        return None

    result = renderer(data)
    return result if result.strip() else None
