"""Reviewer operations: flag lifecycle and vendor detail assembly."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.enums import FlagStatus, ScanStatus, ViewCategory
from app.models.flag import Flag
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_score import HygieneScore
from app.models.product import Product
from app.models.product_ingredient import ProductIngredient
from app.models.stall import Stall
from app.models.stall_image import StallImage
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.reviewer import (
    DetectedIndicatorRead,
    FlagRead,
    HygieneHistoryPoint,
    ScanHistoryRow,
    StallImageRead,
    VendorDetailRead,
)
from app.services.hygiene import hygiene_service
from app.services.hygiene.scoring import score_band

logger = logging.getLogger(__name__)


class ReviewerError(RuntimeError):
    """A reviewer operation that could not be completed."""

    def __init__(self, message: str, user_message: str, not_found: bool = False):
        super().__init__(message)
        self.user_message = user_message
        self.not_found = not_found


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def create_flag(
    db: Session, *, stall: Stall, user: User, reason: str
) -> Flag:
    """Raise a follow-up flag against a stall.

    Multiple open flags on one stall are allowed rather than deduplicated:
    two reviewers noticing two different problems should both be recorded.
    `ReviewerSummary` counts distinct stalls, not flags, so the KPI does not
    double-count.
    """
    flag = Flag(
        stall_id=stall.id,
        reason=reason.strip(),
        status=FlagStatus.OPEN.value,
        created_by_user_id=user.id,
    )
    db.add(flag)
    
    # Audit log
    audit = AuditLog(
        action="flag_created",
        actor_id=user.id,
        target_type="stall",
        target_id=stall.id,
        details={"reason": reason.strip()}
    )
    db.add(audit)
    
    db.commit()
    db.refresh(flag)
    return flag


def resolve_flag(
    db: Session, *, flag: Flag, user: User, note: Optional[str] = None
) -> Flag:
    """Close a flag, recording who did it and when.

    Resolving an already-resolved flag is rejected rather than silently
    re-stamped: overwriting `resolved_by` would destroy the record of who
    actually dealt with it, which is the only reason the field exists.
    """
    if flag.status != FlagStatus.OPEN.value:
        raise ReviewerError(
            f"Flag {flag.id} is already {flag.status}",
            "That flag has already been resolved.",
        )

    flag.status = FlagStatus.RESOLVED.value
    flag.resolved_by_user_id = user.id
    flag.resolved_at = sa.func.now()
    flag.resolution_note = (note or "").strip() or None
    
    # Audit log
    audit = AuditLog(
        action="flag_resolved",
        actor_id=user.id,
        target_type="flag",
        target_id=flag.id,
        details={"stall_id": flag.stall_id, "resolution_note": flag.resolution_note}
    )
    db.add(audit)
    
    db.commit()
    db.refresh(flag)
    return flag


def get_flag(db: Session, flag_id: int) -> Optional[Flag]:
    return db.query(Flag).filter(Flag.id == flag_id).first()


def list_flags(
    db: Session,
    *,
    status: Optional[FlagStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[FlagRead], int]:
    """Flag list, newest first. Defaults to open flags only."""
    query = db.query(Flag)
    if status is not None:
        query = query.filter(Flag.status == status.value)

    total = query.count()
    flags = (
        query.order_by(Flag.created_at.desc(), Flag.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_flag_read(db, flag) for flag in flags], int(total)


def _flag_read(db: Session, flag: Flag) -> FlagRead:
    return FlagRead(
        id=flag.id,
        stall_id=flag.stall_id,
        stall_name=flag.stall.name if flag.stall else None,
        reason=flag.reason,
        status=FlagStatus(flag.status),
        created_by_name=_display_name(flag.created_by),
        created_at=flag.created_at,
        resolved_by_name=_display_name(flag.resolved_by),
        resolved_at=flag.resolved_at,
        resolution_note=flag.resolution_note,
    )


def _display_name(user: Optional[User]) -> Optional[str]:
    """Prefer the full name, fall back to the email local part.

    A reviewer shown as "reviewer3@example.test" is less useful than
    "Priya", but an unnamed account still needs to be attributable.
    """
    if user is None:
        return None
    if user.full_name:
        return user.full_name
    return user.email.split("@")[0] if user.email else None


def open_flags_for_stall(db: Session, stall_id: int) -> List[FlagRead]:
    flags = (
        db.query(Flag)
        .filter(Flag.stall_id == stall_id, Flag.status == FlagStatus.OPEN.value)
        .order_by(Flag.created_at.desc(), Flag.id.desc())
        .all()
    )
    return [_flag_read(db, flag) for flag in flags]


# ---------------------------------------------------------------------------
# Vendor detail
# ---------------------------------------------------------------------------


def _hygiene_history(db: Session, stall_id: int) -> List[HygieneHistoryPoint]:
    rows = (
        db.query(HygieneScore, HygieneCheck.id)
        .join(HygieneCheck, HygieneCheck.id == HygieneScore.hygiene_check_id)
        .filter(HygieneCheck.stall_id == stall_id)
        .order_by(HygieneScore.computed_at.asc(), HygieneScore.id.asc())
        .all()
    )
    return [
        HygieneHistoryPoint(
            check_id=check_id,
            score=score.final_score,
            visual_score=score.visual_score,
            checklist_score=score.checklist_score,
            band=score_band(score.final_score),
            formula_version=score.formula_version,
            assessed_at=score.computed_at,
        )
        for score, check_id in rows
    ]


def _scan_history(db: Session, stall_id: int) -> List[ScanHistoryRow]:
    products = (
        db.query(Product)
        .filter(Product.stall_id == stall_id)
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(100)
        .all()
    )
    if not products:
        return []

    # One grouped count for every scan on the page, rather than a count query
    # per row.
    product_ids = [p.id for p in products]
    counts = dict(
        db.execute(
            sa.select(
                ProductIngredient.product_id, sa.func.count(ProductIngredient.id)
            )
            .where(ProductIngredient.product_id.in_(product_ids))
            .group_by(ProductIngredient.product_id)
        ).all()
    )

    rows: List[ScanHistoryRow] = []
    for product in products:
        if not product.status:
            continue
        try:
            status = ScanStatus(product.status)
        except ValueError:
            # A status this build does not know about; skip rather than
            # render an uncolourable string in the table.
            logger.warning("Unknown status %r on product %s", product.status, product.id)
            continue
        rows.append(
            ScanHistoryRow(
                scan_id=product.id,
                status=status,
                language_code=product.language_code or "en",
                translation_failed=bool(product.translation_failed),
                confidence_score=product.confidence_score,
                ocr_confidence=product.ocr_confidence,
                ingredient_count=int(counts.get(product.id, 0)),
                scanned_at=product.created_at,
            )
        )
    return rows


def _images(db: Session, stall_id: int) -> List[StallImageRead]:
    """Every submitted stall photo, newest first, with its detections.

    One query with the check eagerly loaded, ordered in SQL rather than in
    Python.
    """
    images = (
        db.query(StallImage)
        .join(HygieneCheck, HygieneCheck.id == StallImage.hygiene_check_id)
        .filter(HygieneCheck.stall_id == stall_id)
        .order_by(StallImage.created_at.desc(), StallImage.id.desc())
        .limit(60)
        .all()
    )

    result: List[StallImageRead] = []
    # One catalog lookup for the whole page rather than one per detection.
    names = {
        row.code: row.display_name
        for row in hygiene_service.load_indicator_catalog(db)
    }
    for image in images:
        try:
            view = ViewCategory(image.view_category)
        except ValueError:
            continue

        payload = image.detections or {}
        metrics = payload.get("metrics") or {}
        raw_detections = payload.get("detections") or []

        detections = [
            DetectedIndicatorRead(
                code=entry.get("label", ""),
                display_name=names.get(
                    entry.get("label", ""),
                    str(entry.get("label", "")).replace("_", " ").title(),
                ),
                view=image.view_category,
                confidence=float(entry.get("confidence", 0.0)),
                penalty=0.0,  # penalties are per-check, not per-image
                raw_labels=[entry.get("raw_label")] if entry.get("raw_label") else [],
                bbox=entry.get("bbox"),
            )
            for entry in raw_detections
            if entry.get("bbox")
        ]

        result.append(
            StallImageRead(
                id=image.id,
                check_id=image.hygiene_check_id,
                view_category=view,
                view_display_name=view.display_name,
                image_url=image.image_path,
                detected_at=image.created_at,
                detections=detections,
                box_space=(
                    {
                        "width": float(metrics["image_width"]),
                        "height": float(metrics["image_height"]),
                    }
                    if "image_width" in metrics and "image_height" in metrics
                    else None
                ),
                quality_issues=list((image.quality or {}).get("issues") or []),
            )
        )
    return result


def build_detail(db: Session, stall: Stall, *, include_images: bool = True) -> VendorDetailRead:
    history = _hygiene_history(db, stall.id)
    current = history[-1] if history else None
    previous = history[-2] if len(history) > 1 else None

    return VendorDetailRead(
        stall_id=stall.id,
        stall_name=stall.name,
        food_category=stall.food_category,
        vendor_id=stall.vendor_id,
        vendor_name=(
            stall.vendor.user.full_name
            if stall.vendor and stall.vendor.user
            else None
        ),
        address=stall.address,
        created_at=stall.created_at,
        current_score=current.score if current else None,
        current_band=current.band if current else None,
        # Only when there are two points to compare. A first assessment has
        # no delta, and showing "+63" against an implicit zero would read as
        # a huge improvement that never happened.
        score_delta=(
            round(current.score - previous.score, 2)
            if current and previous
            else None
        ),
        hygiene_history=history,
        scan_history=_scan_history(db, stall.id),
        images=_images(db, stall.id) if include_images else [],
        open_flags=open_flags_for_stall(db, stall.id),
    )


def get_stall_or_404(db: Session, stall_id: int) -> Stall:
    stall = db.query(Stall).filter(Stall.id == stall_id).first()
    if stall is None:
        raise ReviewerError(
            f"Stall {stall_id} not found",
            "That stall was not found.",
            not_found=True,
        )
    return stall
