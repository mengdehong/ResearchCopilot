"""参考文献 ORM (结构化存储, 不做 Embedding)。"""

import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Reference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "references"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    ref_index: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_title: Mapped[str] = mapped_column(Text, nullable=False)
    ref_authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=True,
    )
