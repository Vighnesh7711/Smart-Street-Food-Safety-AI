from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.enums import CheckStatus
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_score import HygieneScore


def get_check(db: Session, check_id: int) -> Optional[HygieneCheck]:
    return (
        db.query(HygieneCheck)
        .options(
            selectinload(HygieneCheck.images),
            selectinload(HygieneCheck.score),
        )
        .filter(HygieneCheck.id == check_id)
        .first()
    )


def list_checks(
    db: Session,
    *,
    stall_ids: Optional[List[int]] = None,
    status: Optional[str] = None,
    include_unfinished: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> List[HygieneCheck]:
    """Most recent first.

    `stall_ids=None` means unscoped (reviewer view); an empty list means no
    stalls and correctly returns nothing rather than everything -- a vendor
    with no stalls must not see the whole table.
    """
    query = db.query(HygieneCheck).options(
        selectinload(HygieneCheck.images),
        selectinload(HygieneCheck.score),
    )

    if stall_ids is not None:
        if not stall_ids:
            return []
        query = query.filter(HygieneCheck.stall_id.in_(stall_ids))

    if status:
        query = query.filter(HygieneCheck.status == status)
    elif not include_unfinished:
        # History reads want completed checks; an abandoned draft with no
        # score is noise in a list of results.
        query = query.filter(HygieneCheck.status == CheckStatus.SCORED.value)

    return (
        query.order_by(HygieneCheck.created_at.desc(), HygieneCheck.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def latest_score_for(db: Session, check_id: int) -> Optional[HygieneScore]:
    return (
        db.query(HygieneScore)
        .filter(HygieneScore.hygiene_check_id == check_id)
        .order_by(HygieneScore.computed_at.desc(), HygieneScore.id.desc())
        .first()
    )
