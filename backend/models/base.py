"""SQLAlchemy ORM 声明基类与通用 Mixin。"""
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""
    pass


class TimestampMixin:
    """created_at / updated_at 自动时间戳。"""
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """UUID 主键 Mixin。"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
