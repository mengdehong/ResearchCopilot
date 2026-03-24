"""Quota API response schemas."""

from pydantic import BaseModel


class WorkspaceQuota(BaseModel):
    """Token usage for a single workspace in the current month."""

    workspace_id: str
    workspace_name: str
    used_tokens: int
    limit_tokens: int


class QuotaStatusResponse(BaseModel):
    """Aggregated token usage across all user workspaces."""

    total_used: int
    total_limit: int
    remaining: int
    usage_percent: float
    workspaces: list[WorkspaceQuota]
