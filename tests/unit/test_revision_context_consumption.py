"""下游 WF 节点 revision_context 消费测试。验证 critique 打回后反馈真正注入 LLM prompt。"""

import json
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from backend.agent.workflows.execution.nodes import GeneratedCode, generate_code
from backend.agent.workflows.extraction.nodes import GeneratedNote, generate_notes
from backend.agent.workflows.ideation.nodes import DecomposedProblem, SubProblem, decompose_problem

# ── extraction: generate_notes 消费 revision_context ──


def _make_mock_llm_for(output_model: type[BaseModel], return_value: BaseModel) -> MagicMock:
    """构建 mock LLM，拦截 with_structured_output 链式调用。"""
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(return_value=return_value)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.unit
def test_extraction_generate_notes_includes_revision_context() -> None:
    """generate_notes 存在 revision_context 时应注入 revision_feedback 到 LLM input。"""
    note = GeneratedNote(
        key_contributions=["c1"],
        methodology="m",
        experimental_setup="e",
        main_results="r",
        limitations=["l1"],
    )
    llm = _make_mock_llm_for(GeneratedNote, note)

    state = {
        "paper_ids": ["paper_1"],
        "artifacts": {
            "discovery": {"papers": [{"arxiv_id": "paper_1", "title": "T", "abstract": "A"}]}
        },
        "retrieved_chunks": [],
        "reading_notes": [],
        "revision_context": "- [major] methodology: Missing baseline → Add ablation",
    }

    generate_notes(state, llm=llm)

    # 验证 LLM invoke 的 HumanMessage 包含 revision_feedback
    invoke_args = llm.with_structured_output.return_value.invoke.call_args
    human_msg = invoke_args[0][0][1]  # messages[1] = HumanMessage
    payload = json.loads(human_msg.content)
    assert "revision_feedback" in payload
    assert "Missing baseline" in payload["revision_feedback"]


@pytest.mark.unit
def test_extraction_generate_notes_no_revision_context() -> None:
    """无 revision_context 时不应注入 revision_feedback。"""
    note = GeneratedNote(
        key_contributions=["c1"],
        methodology="m",
        experimental_setup="e",
        main_results="r",
        limitations=["l1"],
    )
    llm = _make_mock_llm_for(GeneratedNote, note)

    state = {
        "paper_ids": ["paper_1"],
        "artifacts": {
            "discovery": {"papers": [{"arxiv_id": "paper_1", "title": "T", "abstract": "A"}]}
        },
        "retrieved_chunks": [],
        "reading_notes": [],
    }

    generate_notes(state, llm=llm)

    invoke_args = llm.with_structured_output.return_value.invoke.call_args
    human_msg = invoke_args[0][0][1]
    payload = json.loads(human_msg.content)
    assert "revision_feedback" not in payload


# ── ideation: analyze_gaps 消费 revision_context ──


@pytest.mark.unit
def test_ideation_decompose_problem_includes_revision_context() -> None:
    """decompose_problem 存在 revision_context 时应注入 revision_feedback 到 LLM input。"""
    decomp = DecomposedProblem(
        sub_problems=[SubProblem(question="q1", relevant_papers=["p1"], aspect="methodology")],
        overall_theme="test theme",
    )
    llm = _make_mock_llm_for(DecomposedProblem, decomp)

    state = {
        "artifacts": {"extraction": {"reading_notes": [], "glossary": {}}},
        "revision_context": "- [minor] clarity: Unclear hypothesis → Reword",
    }

    decompose_problem(state, llm=llm)

    invoke_args = llm.with_structured_output.return_value.invoke.call_args
    human_msg = invoke_args[0][0][1]
    payload = json.loads(human_msg.content)
    assert "revision_feedback" in payload
    assert "Unclear hypothesis" in payload["revision_feedback"]


# ── execution: generate_code 消费 revision_context ──


@pytest.mark.unit
def test_execution_generate_code_includes_revision_context() -> None:
    """generate_code 存在 revision_context 时应注入审稿反馈到 prompt。"""
    code_result = GeneratedCode(code="print(1)", description="test")
    llm = _make_mock_llm_for(GeneratedCode, code_result)

    state = {
        "task_description": "run experiment",
        "artifacts": {"ideation": {"experiment_design": {}}},
        "revision_context": "- [major] code: Missing error handling → Add try/except",
    }

    generate_code(state, llm=llm)

    invoke_args = llm.with_structured_output.return_value.invoke.call_args
    human_msg = invoke_args[0][0][1]
    assert "审稿反馈" in human_msg.content
    assert "Missing error handling" in human_msg.content
