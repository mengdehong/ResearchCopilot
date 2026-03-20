"""Agent Workflows 入口。导出所有 WF 构建函数。"""

from backend.agent.workflows.critique.graph import build_critique_graph
from backend.agent.workflows.discovery.graph import build_discovery_graph
from backend.agent.workflows.execution.graph import build_execution_graph
from backend.agent.workflows.extraction.graph import build_extraction_graph
from backend.agent.workflows.ideation.graph import build_ideation_graph
from backend.agent.workflows.publish.graph import build_publish_graph

__all__ = [
    "build_critique_graph",
    "build_discovery_graph",
    "build_execution_graph",
    "build_extraction_graph",
    "build_ideation_graph",
    "build_publish_graph",
]
