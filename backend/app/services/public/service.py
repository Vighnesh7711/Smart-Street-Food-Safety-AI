"""Assembles the public stall profile.

Read-only, and deliberately narrow: it reads the stall, its latest hygiene
score, and its latest label scan, and maps them into the allow-list schema.
It never touches the user, vendor, image, or document tables.

The shape of this module is a small privacy boundary. Anything added here
becomes visible to anyone who scans a sticker, so the queries are written to
select from the minimum set of tables that answer the question.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.crud import qr_code as crud_qr_code
from app.models.enums import ScanStatus
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_score import HygieneScore
from app.models.product import Product
from app.models.stall import Stall
from app.schemas.public import (
    PublicHygieneSummary,
    PublicScanSummary,
    PublicStallProfile,
)
from app.services.hygiene.scoring import score_band

logger = logging.getLogger(__name__)


def _latest_hygiene(db: Session, stall_id: int) -> Optional[PublicHygieneSummary]:
    """Most recent computed hygiene score for a stall, or None.

    Ordered by `computed_at` then `id` so two scores written in the same
    transaction still have a deterministic "latest".
    """
    score = (
        db.query(HygieneScore)
        .join(HygieneCheck, HygieneCheck.id == HygieneScore.hygiene_check_id)
        .filter(HygieneCheck.stall_id == stall_id)
        .order_by(HygieneScore.computed_at.desc(), HygieneScore.id.desc())
        .first()
    )
    if score is None:
        return None

    return PublicHygieneSummary(
        score=score.final_score,
        band=score_band(score.final_score),
        assessed_at=score.computed_at,
    )


def _latest_scan(db: Session, stall_id: int) -> Optional[PublicScanSummary]:
    """Most recent product-label check for a stall.

    Only the status and the date leave this function -- see
    PublicScanSummary for why the product name does not.
    """
    product = (
        db.query(Product)
        .filter(Product.stall_id == stall_id)
        .order_by(Product.created_at.desc(), Product.id.desc())
        .first()
    )
    if product is None or not product.status:
        return None

    try:
        status = ScanStatus(product.status)
    except ValueError:
        # A status written by a future version this build does not know
        # about. Reporting nothing is better than reporting a raw string the
        # public page cannot render or colour.
        logger.warning("Unknown product status %r on product %s", product.status, product.id)
        return None

    return PublicScanSummary(status=status, scanned_at=product.created_at)


def build_profile(db: Session, stall: Stall) -> PublicStallProfile:
    return PublicStallProfile(
        stall_name=stall.name,
        food_category=stall.food_category,
        hygiene=_latest_hygiene(db, stall.id),
        last_scan=_latest_scan(db, stall.id),
    )


def get_by_code(db: Session, code: str) -> Optional[PublicStallProfile]:
    """Resolve a public code to its profile, or None.

    None covers both "no such code" and "that code was revoked", because the
    endpoint answers both with an identical 404 -- the response must not
    reveal which of the two it was.
    """
    stall = crud_qr_code.get_stall_by_code(db, code)
    if stall is None:
        return None
    return build_profile(db, stall)


from app.models.consumer_report import ConsumerReport
from app.schemas.public import PublicStallLocation, ConsumerReportCreate

def list_stalls_for_map(db: Session) -> list[PublicStallLocation]:
    """Get all stalls that have a location and an active QR code, mapped for the consumer dashboard."""
    locations = []
    # We only want stalls with latitude and longitude
    stalls = db.query(Stall).filter(Stall.latitude.isnot(None), Stall.longitude.isnot(None)).all()
    for stall in stalls:
        qr_code = stall.qr_code_id
        if qr_code:
            hygiene = _latest_hygiene(db, stall.id)
            locations.append(
                PublicStallLocation(
                    stall_name=stall.name,
                    latitude=stall.latitude,
                    longitude=stall.longitude,
                    code=qr_code,
                    score=hygiene.score if hygiene else None,
                    band=hygiene.band if hygiene else None,
                )
            )
    return locations

def create_consumer_report(db: Session, code: str, report_in: ConsumerReportCreate) -> bool:
    """Create a consumer report for a stall. Returns True if successful, False if stall not found."""
    stall = crud_qr_code.get_stall_by_code(db, code)
    if not stall:
        return False
    
    report = ConsumerReport(
        stall_id=stall.id,
        category=report_in.category,
        notes=report_in.notes
    )
    db.add(report)
    db.commit()
    return True
