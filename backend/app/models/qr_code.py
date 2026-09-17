"""QR codes issued to stalls.

Phase 1 stored the code as `stalls.qr_code_id`. Phase 4 moves it here so
there is exactly one source of truth.

WHY THIS IS A TABLE AND NOT A COLUMN
------------------------------------
A QR sticker is a *printed artefact*. It is stuck to a stall, photographed,
and possibly reprinted. That means its lifecycle is real: a code gets issued,
may be revoked (stall re-registered, sticker leaked, vendor changed), and a
replacement may be issued.

If the code lived on `stalls` as a column, then issuing a replacement would
either overwrite it (breaking nothing, but losing the history of what was
printed) or require a second column for "old codes" -- which is this table
with extra steps. More importantly, any scheme that keeps a copy on `stalls`
and a copy here can disagree, and when they disagree a printed sticker
silently stops resolving.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class QrCode(Base):
    """One issued stall code.

    `code` is what appears in the public URL and inside the QR image. It is
    generated from a look-alike-free alphabet (no I, L, O, U) because these
    are read aloud, typed from a damaged sticker, and pasted into a browser.
    """

    __tablename__ = "qr_codes"
    __table_args__ = (
        # At most one ACTIVE code per stall. A plain UNIQUE(stall_id) would
        # forbid ever issuing a replacement, which defeats the point of the
        # table; a partial unique index allows history while still making
        # "revoke the old one, then issue the new one" safe under concurrency.
        #
        # Both dialects are declared so the SQLite-backed tests exercise the
        # same constraint the migration creates in PostgreSQL.
        Index(
            "uq_qr_codes_active_stall",
            "stall_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    stall_id = Column(
        Integer, ForeignKey("stalls.id", ondelete="CASCADE"), nullable=False
    )

    code = Column(String(16), unique=True, index=True, nullable=False)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    stall = relationship("Stall", back_populates="qr_codes")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        state = "active" if self.is_active else "revoked"
        return f"<QrCode {self.code!r} stall={self.stall_id} {state}>"
