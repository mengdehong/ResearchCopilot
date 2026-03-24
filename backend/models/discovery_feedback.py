"""Discovery HITL 反馈 ORM 模型。记录用户在 present_candidates 节点的勾选行为。"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiscoveryFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discovery WF 的 HITL 隐式反馈记录。

    每次用户从候选论文中勾选要深读的论文，写入一条记录，
    供 DSPy 离线训练 filter_and_rank 模块使用。
    """

    __tablename__ = "discovery_feedback"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    discipline: Mapped[str] = mapped_column(Text, nullable=False)
    candidates_json: Mapped[str] = mapped_column(Text, nullable=False)
    selected_paper_ids: Mapped[str] = mapped_column(Text, nullable=False)
