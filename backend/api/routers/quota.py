"""Quota API router — expose token usage stats to the frontend."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.quota import QuotaStatusResponse, WorkspaceQuota
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.services.quota_service import get_quota_status

router = APIRouter(prefix="/api/quota", tags=["quota"])


@router.get("/status", response_model=QuotaStatusResponse)
async def quota_status(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuotaStatusResponse:
    """Return aggregated token usage for all workspaces owned by the current user."""
    stmt = select(Workspace).where(
        Workspace.owner_id == current_user.id,
        Workspace.is_deleted.is_(False),
    )
    result = await session.execute(stmt)
    workspaces = result.scalars().all()

    ws_quotas: list[WorkspaceQuota] = []
    total_used = 0
    total_limit = 0

    for ws in workspaces:
        status = await get_quota_status(session, ws.id)
        ws_quotas.append(
            WorkspaceQuota(
                workspace_id=str(ws.id),
                workspace_name=ws.name,
                used_tokens=status.used_tokens,
                limit_tokens=status.limit_tokens,
            )
        )
        total_used += status.used_tokens
        total_limit += status.limit_tokens

    remaining = max(0, total_limit - total_used)
    usage_percent = (total_used / total_limit * 100) if total_limit > 0 else 0.0

    return QuotaStatusResponse(
        total_used=total_used,
        total_limit=total_limit,
        remaining=remaining,
        usage_percent=round(usage_percent, 2),
        workspaces=ws_quotas,
    )
