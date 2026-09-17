from typing import Optional

from sqlalchemy.orm import Session

from app.models.qr_code import QrCode
from app.models.stall import Stall
from app.services.qr.service import normalize_code


def get_qr_code(db: Session, qr_code_id: int) -> Optional[QrCode]:
    return db.query(QrCode).filter(QrCode.id == qr_code_id).first()


def get_active_for_stall(db: Session, stall_id: int) -> Optional[QrCode]:
    return (
        db.query(QrCode)
        .filter(QrCode.stall_id == stall_id, QrCode.is_active.is_(True))
        .first()
    )


def get_stall_by_code(db: Session, code: str) -> Optional[Stall]:
    """Resolve a public code to its stall, active codes only.

    Returns None for unknown AND revoked codes so callers can answer both
    with an identical 404 -- the response must not reveal which of the two
    it was.
    """
    normalized = normalize_code(code)
    if not normalized:
        return None
    return (
        db.query(Stall)
        .join(QrCode, QrCode.stall_id == Stall.id)
        .filter(QrCode.code == normalized, QrCode.is_active.is_(True))
        .first()
    )
