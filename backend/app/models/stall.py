from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

# Imported for its side effect: registering the Flag mapper. The relationship
# below names Flag by string, and SQLAlchemy resolves that at configuration
# time -- so importing this module alone must also pull Flag in, or a test
# that imports only the models it needs fails with "name 'Flag' is not
# defined". There is no cycle: flag.py names Stall by string and imports
# nothing from here.
from app.models.flag import Flag  # noqa: F401


class Stall(Base):
    __tablename__ = "stalls"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    name = Column(String, index=True, nullable=False)
    food_category = Column(String, nullable=True)

    # Location
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Metrics
    hygiene_score = Column(Float, nullable=True)
    # Removed in Phase 5: `is_flagged` (0/1) was never written by anything and
    # only ever serialized as false. Whether a stall is flagged is now derived
    # from the `flags` table, which carries the reason, reviewer, and
    # resolution that a boolean cannot.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    vendor = relationship("Vendor", back_populates="stalls")
    products = relationship("Product", back_populates="stall")
    flags = relationship(
        "Flag",
        back_populates="stall",
        cascade="all, delete-orphan",
        # String form avoids importing Flag here (which would make the
        # import order between the two model modules load-bearing). Written
        # as an attribute-method chain rather than "desc(Flag.created_at)":
        # the string is evaluated in a namespace holding the mapped classes,
        # not the sqlalchemy functions.
        order_by="Flag.created_at.desc()",
    )
    qr_codes = relationship(
        "QrCode",
        back_populates="stall",
        cascade="all, delete-orphan",
        order_by="QrCode.id",
        # selectin rather than the default lazy load: `qr_code_id` below reads
        # this relationship, and StallRead serializes it, so listing stalls
        # would otherwise issue one SELECT per stall.
        lazy="selectin",
    )

    @property
    def has_open_flag(self) -> bool:
        """True when any flag on this stall is still open.

        Derived from the relationship, not stored. The reviewer table loads
        open flags in bulk (see crud/reviewer.py) rather than calling this per
        row, so it exists for serialization and single-stall reads.
        """
        return any(flag.is_open for flag in self.flags)

    @property
    def qr_code_id(self) -> str | None:
        """The stall's active QR code, or None if none is active.

        Derived, not stored. Phase 1 kept this as a column on `stalls`; since
        Phase 4 it lives in `qr_codes` so that issuing a replacement cannot
        leave two disagreeing copies -- which would silently break a printed
        sticker.

        Still exposed on `StallRead`, so the API contract is unchanged. None
        is possible in principle (a stall whose only code was revoked), which
        is why the schema types it as optional.
        """
        for qr_code in self.qr_codes:
            if qr_code.is_active:
                return qr_code.code
        return None

    @property
    def active_qr_code(self):
        """The active QrCode row, for callers that need more than the string."""
        for qr_code in self.qr_codes:
            if qr_code.is_active:
                return qr_code
        return None
