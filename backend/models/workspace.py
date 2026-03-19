"""课题空间 ORM。"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspaces"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    discipline: Mapped[str] = mapped_column(
        Text, server_default="computer_science", nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
