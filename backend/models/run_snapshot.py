"""Run 输入快照 ORM。"""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RunSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "run_snapshots"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False,
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    editor_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text, server_default="running", nullable=False,
    )
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
