"""Agent State 定义。SharedState 共享基座 + 各 WF 私有扩展。"""

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel

WorkflowName = Literal[
    "discovery",
    "extraction",
    "ideation",
    "execution",
    "critique",
    "publish",
]

# ── Reducer ──


def merge_dicts(left: dict, right: dict) -> dict:
    """深度合并字典，右侧覆盖同名 key。"""
    merged = {**left}
    for key, value in right.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


# ── SharedState ──


class SharedState(TypedDict):
    """所有图的共享基座。只包含 4 个字段，永不扩充。"""

    messages: Annotated[list, add_messages]
    workspace_id: str
    discipline: str
    artifacts: Annotated[dict, merge_dicts]


# ── Supervisor State ──


class PlannedStep(BaseModel):
    workflow: WorkflowName
    objective: str
    success_criteria: str


class ExecutionPlan(BaseModel):
    steps: list[PlannedStep]
    goal: str


class SupervisorState(SharedState):
    plan: ExecutionPlan | None
    current_step_index: int
    routing_decision: str | None


# ── Workflow States ──


class PaperCard(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    year: int
    citation_count: int | None = None
    relevance_score: float
    relevance_comment: str  # LLM 一句话相关性评语，供 HITL 勾选参考
    source: str


class DiscoveryState(SharedState):
    search_queries: list[str]
    raw_results: list[dict]
    candidate_papers: list[PaperCard]
    selected_paper_ids: list[str]  # 用户 HITL 勾选的论文 ID
    ingestion_task_ids: list[str]  # Celery ingestion 任务 ID


class ReadingNote(BaseModel):
    paper_id: str
    key_contributions: list[str]
    methodology: str
    experimental_setup: str
    main_results: str
    limitations: list[str]
    source_chunks: list[str]


class ComparisonEntry(BaseModel):
    paper_id: str
    method: str
    dataset: str
    metric_values: dict[str, float]
    key_difference: str


class ExtractionState(SharedState):
    paper_ids: list[str]
    reading_notes: list[ReadingNote]
    comparison_matrix: list[ComparisonEntry]
    glossary: dict[str, str]


class ResearchGap(BaseModel):
    description: str
    supporting_evidence: list[str]
    potential_impact: str


class ExperimentDesign(BaseModel):
    hypothesis: str
    method_description: str
    baselines: list[str]
    datasets: list[str]
    evaluation_metrics: list[str]
    expected_outcome: str


class IdeationState(SharedState):
    research_gaps: list[ResearchGap]
    experiment_designs: list[ExperimentDesign]
    selected_design_index: int | None


class SandboxExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    output_files: list[str]
    execution_time_seconds: float


class ExecutionState(SharedState):
    task_description: str
    generated_code: str
    execution_result: SandboxExecutionResult | None
    retry_count: int
    reflection: str | None
    elapsed_seconds: float
    tokens_used: int


class CritiqueFeedback(BaseModel):
    category: str
    severity: str
    description: str
    suggestion: str
    location: str | None = None


class CritiqueState(SharedState):
    target_workflow: str
    supporter_opinion: str
    critic_opinion: str
    feedbacks: list[CritiqueFeedback]
    verdict: str
    critique_round: int


class OutlineSection(BaseModel):
    title: str
    description: str
    source_artifacts: list[str]


class PublishState(SharedState):
    outline: list[OutlineSection]
    markdown_content: str
    user_edited_markdown: str | None  # Canvas 手改后回流的 Markdown
    citation_map: dict[str, str]
    output_files: list[str]
