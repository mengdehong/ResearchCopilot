"""图表 ORM。"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Figure(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "figures"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    section_path: Mapped[str] = mapped_column(Text, nullable=False)
    caption_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
