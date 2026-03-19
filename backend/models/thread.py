"""对话 Thread ORM（本地镜像）。"""
import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Thread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "threads"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, server_default="New Thread", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="creating", nullable=False)
    langgraph_thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
