"""Prompt 覆盖层 ORM。"""

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PromptOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_overrides"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, server_default="manual", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
