"""PPT 生成 Skill subgraph 测试。覆盖各节点函数和图编译。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agent.skills.ppt_generation.execute import (
    PPTGenerationState,
    build_ppt_graph,
    confirm_outline,
    fill_content,
    plan_outline,
    render_node,
)
from backend.agent.skills.ppt_generation.schema import (
    BulletsContent,
    PresentationMeta,
    PresentationSchema,
    SlideSchema,
)


def _make_mock_llm(responses: list) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_test_schema() -> PresentationSchema:
    return PresentationSchema(
        meta=PresentationMeta(
            scene="paper_presentation",
            title="Test",
            authors=["A"],
        ),
        slides=[
            SlideSchema(
                id="s1",
                layout="bullets",
                section="Intro",
                content=BulletsContent(heading="H", points=["P"]),
            ),
        ],
    )


# ── plan_outline ──


def test_plan_outline_returns_schema() -> None:
    schema = _make_test_schema()
    llm = _make_mock_llm([schema])
    state: PPTGenerationState = {
        "content_sections": {"extraction": {"notes": "data"}},
        "scene": "paper_presentation",
        "template_name": "academic_blue",
        "backend": "typst",
        "outline_schema": None,
        "full_schema": None,
        "rendered": None,
    }
    result = plan_outline(state, llm=llm)
    assert result["outline_schema"] is not None
    assert result["outline_schema"].meta.title == "Test"


# ── confirm_outline (HITL) ──


def test_confirm_outline_approve() -> None:
    schema = _make_test_schema()
    state: PPTGenerationState = {
        "content_sections": {},
        "scene": "paper_presentation",
        "template_name": "academic_blue",
        "backend": "typst",
        "outline_schema": schema,
        "full_schema": None,
        "rendered": None,
    }
    with patch(
        "backend.agent.skills.ppt_generation.execute.interrupt",
        return_value={"decision": "approve"},
    ):
        result = confirm_outline(state)
    assert result == {}


def test_confirm_outline_reject_with_modified() -> None:
    schema = _make_test_schema()
    modified = _make_test_schema()
    modified.meta.title = "Modified Title"
    state: PPTGenerationState = {
        "content_sections": {},
        "scene": "paper_presentation",
        "template_name": "academic_blue",
        "backend": "typst",
        "outline_schema": schema,
        "full_schema": None,
        "rendered": None,
    }
    with patch(
        "backend.agent.skills.ppt_generation.execute.interrupt",
        return_value={"modified_schema": modified.model_dump()},
    ):
        result = confirm_outline(state)
    assert result["outline_schema"].meta.title == "Modified Title"


# ── fill_content ──


def test_fill_content_returns_full_schema() -> None:
    full_schema = _make_test_schema()
    llm = _make_mock_llm([full_schema])
    state: PPTGenerationState = {
        "content_sections": {"extraction": {"notes": "data"}},
        "scene": "paper_presentation",
        "template_name": "academic_blue",
        "backend": "typst",
        "outline_schema": _make_test_schema(),
        "full_schema": None,
        "rendered": None,
    }
    result = fill_content(state, llm=llm)
    assert result["full_schema"] is not None


# ── render_node ──


def test_render_node_generates_source(tmp_path: Path) -> None:
    schema = _make_test_schema()
    state: PPTGenerationState = {
        "content_sections": {},
        "scene": "paper_presentation",
        "template_name": "academic_blue",
        "backend": "typst",
        "outline_schema": schema,
        "full_schema": schema,
        "rendered": None,
    }
    mock_uuid = MagicMock()
    mock_uuid.hex = "12345678abcdefab"
    with (
        patch(
            "backend.agent.skills.ppt_generation.execute.TEMPLATES_DIR",
            Path(__file__).resolve().parents[2] / "backend/agent/skills/ppt_generation/templates",
        ),
        patch(
            "backend.agent.skills.ppt_generation.execute.uuid.uuid4",
            return_value=mock_uuid,
        ),
    ):
        result = render_node(state)

    assert result["rendered"] is not None
    assert result["rendered"].source_type == "typst"


# ── subgraph 编译 ──


def test_ppt_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_ppt_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "plan_outline" in node_names
    assert "confirm_outline" in node_names
    assert "fill_content" in node_names
    assert "render" in node_names
