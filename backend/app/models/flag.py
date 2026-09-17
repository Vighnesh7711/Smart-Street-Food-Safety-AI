"""Reviewer flags: a stall a reviewer wants followed up.

Phase 1 put a boolean `stalls.is_flagged` on the stall. Nothing ever wrote
it; it was read only by the serializer, which always produced `false`. Phase
5 replaces it with this table, which actually carries the information a
reviewer needs -- why, who, when, and whether it has been dealt with.

Keeping the boolean alongside would have created a second, unmaintained
answer to "is this stall flagged", free to drift from this one.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.models.enums import FlagStatus


class Flag(Base):
    """One follow-up flag raised against a stall.

    Flags attach to a STALL, not a vendor: the reviewer table is one row per
    stall, and every column it shows (hygiene score, last scan) is that
    stall's own record. A flag therefore points at the thing that was
    actually observed.
    """

    __tablename__ = "flags"
    __table_args__ = (
        # The dashboard's hot query is "which stalls are currently flagged".
        # A partial index keeps that cheap no matter how much resolved
        # history accumulates -- it never has to look at closed rows.
        Index(
            "ix_flags_open",
            "stall_id",
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    stall_id = Column(
        Integer, ForeignKey("stalls.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: Required. A flag with no reason is not actionable by whoever picks it
    #: up later, which defeats the purpose of recording it.
    reason = Column(Text, nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default=FlagStatus.OPEN.value,
        index=True,
    )

    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    resolved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)

    stall = relationship("Stall", back_populates="flags")
    # Two FKs to the same table, so each relationship names its own column
    # explicitly -- without foreign_keys, SQLAlchemy cannot tell them apart.
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])

    @property
    def is_open(self) -> bool:
        return self.status == FlagStatus.OPEN.value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Flag {self.id} stall={self.stall_id} {self.status}>"
