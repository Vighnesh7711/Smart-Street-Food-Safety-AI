"""Hygiene check orchestration.

    create draft
      -> upload one photo per required view   (coverage validated as we go)
      -> vendor answers the checklist
      -> complete: run CV on all four, score, persist

Detection runs at *completion*, not per upload, because the spec requires a
complete set before any indicator detection happens -- and because a retake
replaces the image for its view, so detecting early would leave stale
findings behind.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.config import settings
from app.integrations import cv_client
from app.models.enums import CheckStatus, UserRole, ViewCategory
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_indicator import HygieneIndicator
from app.models.hygiene_score import HygieneScore
from app.models.stall import Stall
from app.models.stall_image import StallImage
from app.models.user import User
from app.services.hygiene import checklist as checklist_service
from app.services.hygiene import coverage as coverage_service
from app.services.hygiene import duplicate as duplicate_service
from app.services.hygiene import indicators as indicator_service
from app.services.hygiene import scoring as scoring_service
from app.services.hygiene.indicators import IndicatorFinding

# Reused deliberately: the gate is domain-agnostic (blur, exposure, glare are
# the same problem for a stall photo as for a label photo). It reads the
# SCAN_* threshold settings, which are physically meaningful for both. If a
# third consumer appears, promote it to a shared services/imaging/ package.
from app.services.products import image_quality

logger = logging.getLogger(__name__)


class HygieneError(RuntimeError):
    """A hygiene operation could not be completed.

    Carries a vendor-safe `user_message` and a `retryable` hint, matching
    the scan pipeline's error contract so the API layer can map both to the
    same shape.
    """

    def __init__(self, message: str, user_message: str, retryable: bool = False):
        super().__init__(message)
        self.user_message = user_message
        self.retryable = retryable


@dataclass
class UploadResult:
    image: StallImage
    coverage: coverage_service.CoverageStatus
    check: HygieneCheck
    quality_issues: List[str] = field(default_factory=list)


@dataclass
class CompletionResult:
    check: HygieneCheck
    score: HygieneScore
    findings: List[IndicatorFinding]
    checklist_rows: List[dict]


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def load_indicator_catalog(db: Session) -> List[HygieneIndicator]:
    return (
        db.query(HygieneIndicator)
        .filter(HygieneIndicator.is_active.is_(True))
        .order_by(HygieneIndicator.id)
        .all()
    )


def checklist_catalog() -> List[dict]:
    """The checklist questions, for the mobile form."""
    return [
        {"code": item.code, "label": item.label, "help_text": item.help_text}
        for item in checklist_service.SEED_CHECKLIST_ITEMS
    ]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def create_check(db: Session, *, stall: Stall, user: User) -> HygieneCheck:
    """Open a draft check and return it.

    Idempotent in a useful way: if the vendor already has an unfinished
    check for this stall, that one is returned instead of creating a second.
    Otherwise abandoning the app mid-flow and reopening it would litter the
    history with empty drafts.
    """
    existing = (
        db.query(HygieneCheck)
        .filter(
            HygieneCheck.stall_id == stall.id,
            HygieneCheck.status.in_(
                [CheckStatus.DRAFT.value, CheckStatus.AWAITING_VIEWS.value]
            ),
        )
        .order_by(HygieneCheck.created_at.desc(), HygieneCheck.id.desc())
        .first()
    )
    if existing is not None:
        return existing

    check = HygieneCheck(
        stall_id=stall.id,
        submitted_by_user_id=user.id,
        status=CheckStatus.DRAFT.value,
        missing_views=[view.value for view in ViewCategory],
        coverage_ok=False,
        indicators_found=[],
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def add_view_image(
    db: Session,
    *,
    check: HygieneCheck,
    view: ViewCategory,
    image_bytes: bytes,
) -> UploadResult:
    """Attach one view photo, rejecting a duplicate of another view.

    Raises HygieneError if the image is unusable or duplicates an existing
    view. The duplicate check is scoped to this check (see duplicate.py).
    """
    if check.status == CheckStatus.SCORED.value:
        raise HygieneError(
            "Check already scored",
            "This check is already complete. Start a new check to submit "
            "fresh photos.",
        )

    _validate_upload(image_bytes)

    quality = image_quality.assess(image_bytes)
    if not quality.ok:
        # Rejected before storing, so the vendor can retake without the bad
        # photo entering the record.
        raise HygieneError(
            f"Image quality rejected for {view.value}: {quality.issues}",
            quality.guidance or "That photo was not clear enough. Please retake it.",
        )

    existing_images = (
        db.query(StallImage).filter(StallImage.hygiene_check_id == check.id).all()
    )
    decoded = cv_client.decode_image(image_bytes)
    phash = duplicate_service.dhash(decoded)

    duplicate = duplicate_service.find_duplicate(
        phash,
        [(img.id, img.phash or "") for img in existing_images],
        settings.CV_DUPLICATE_HAMMING_THRESHOLD,
    )
    if duplicate is not None:
        duplicate_id, distance = duplicate
        other = next((i for i in existing_images if i.id == duplicate_id), None)
        other_view = other.view_category if other else "another"
        raise HygieneError(
            f"Duplicate image for {view.value} (distance {distance} to image {duplicate_id})",
            f"This looks like the same photo you already submitted for the "
            f"{other_view.replace('_', ' ')}. Each view needs its own photo.",
        )

    image_path = _store_image(image_bytes)

    # A retake replaces the image for its view: it would be wrong for an
    # older, worse photo to keep contributing to the score.
    previous = next((i for i in existing_images if i.view_category == view.value), None)
    if previous is not None:
        previous.image_path = image_path
        previous.quality = quality.to_dict()
        previous.phash = phash
        previous.detections = None
        image = previous
    else:
        image = StallImage(
            hygiene_check_id=check.id,
            stall_id=check.stall_id,
            view_category=view.value,
            image_path=image_path,
            quality=quality.to_dict(),
            phash=phash,
        )
        db.add(image)

    db.flush()

    present = [i.view_category for i in existing_images if i.id != image.id]
    present.append(view.value)
    status = coverage_service.evaluate_coverage(present)

    check.missing_views = [v.value for v in status.missing]
    check.coverage_ok = status.ok
    # Every upload leaves the check awaiting views -- including the fourth,
    # which still needs the checklist and an explicit completion before it is
    # scored.
    check.status = CheckStatus.AWAITING_VIEWS.value

    db.commit()
    db.refresh(image)
    db.refresh(check)

    return UploadResult(
        image=image, coverage=status, check=check, quality_issues=quality.issues
    )


def submit_checklist(
    db: Session, *, check: HygieneCheck, answers: Dict[str, bool]
) -> HygieneCheck:
    """Store the vendor's self-declared answers.

    Allowed before coverage is complete so the order of the mobile flow is
    flexible. Unknown codes are stored but ignored by scoring, which
    `score_checklist` reports via `ignored_codes`.
    """
    if check.status == CheckStatus.SCORED.value:
        raise HygieneError(
            "Check already scored",
            "This check is already complete and cannot be changed.",
        )

    check.checklist = {str(k): bool(v) for k, v in (answers or {}).items()}
    db.commit()
    db.refresh(check)
    return check


def complete_check(db: Session, *, check: HygieneCheck) -> CompletionResult:
    """Run detection across all views, score, and persist.

    Requires complete coverage. Partial runs would produce a score that
    looks authoritative while being based on less than the full picture.
    """
    if check.status == CheckStatus.SCORED.value:
        raise HygieneError(
            "Check already scored", "This check has already been scored."
        )

    images = (
        db.query(StallImage)
        .filter(StallImage.hygiene_check_id == check.id)
        .order_by(StallImage.id)
        .all()
    )
    status = coverage_service.evaluate_coverage([i.view_category for i in images])
    if not status.ok:
        check.missing_views = [v.value for v in status.missing]
        db.commit()
        raise HygieneError(
            f"Incomplete coverage: {status.missing}",
            status.message or "Some photos are still missing.",
        )

    catalog = load_indicator_catalog(db)
    detections_by_view: Dict[str, List[cv_client.Detection]] = {}

    for image in images:
        try:
            with open(settings.hygiene_upload_path / _filename(image.image_path), "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            logger.error("Could not read stored image %s: %s", image.image_path, exc)
            raise HygieneError(
                f"Missing stored image {image.image_path}",
                "One of your photos could not be read. Please retake it.",
            ) from exc

        try:
            result = cv_client.run_detection(
                raw, ViewCategory(image.view_category), catalog
            )
        except cv_client.CvError as exc:
            logger.error("CV failed for image %s: %s", image.id, exc)
            check.status = CheckStatus.FAILED.value
            db.commit()
            raise HygieneError(str(exc), exc.user_message, retryable=exc.retryable) from exc

        image.detections = result.to_dict()
        detections_by_view[image.view_category] = result.detections

    findings = indicator_service.build_findings(detections_by_view, catalog)

    checklist_score, checklist_breakdown = checklist_service.score_checklist(
        check.checklist
    )
    score_result = scoring_service.compute_score(findings, checklist_score)

    breakdown = dict(score_result.breakdown)
    breakdown["checklist"] = checklist_breakdown

    score = HygieneScore(
        hygiene_check_id=check.id,
        visual_score=score_result.visual_score,
        checklist_score=score_result.checklist_score,
        final_score=score_result.final_score,
        breakdown=breakdown,
        weights=score_result.weights,
        formula_version=score_result.formula_version,
    )
    db.add(score)

    check.indicators_found = indicator_service.summarise_for_storage(findings)
    check.status = CheckStatus.SCORED.value
    check.missing_views = []
    check.coverage_ok = True
    check.scored_at = func.now()

    # Keep the denormalised column on stalls in step, in the same
    # transaction as the score row, so the two cannot drift apart.
    stall = db.query(Stall).filter(Stall.id == check.stall_id).first()
    if stall is not None:
        stall.hygiene_score = score_result.final_score

    db.commit()
    db.refresh(score)
    db.refresh(check)

    return CompletionResult(
        check=check,
        score=score,
        findings=findings,
        checklist_rows=checklist_service.describe_checklist(check.checklist),
    )


def latest_score(db: Session, check_id: int) -> Optional[HygieneScore]:
    return (
        db.query(HygieneScore)
        .filter(HygieneScore.hygiene_check_id == check_id)
        .order_by(HygieneScore.computed_at.desc(), HygieneScore.id.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _filename(image_path: str) -> str:
    return image_path.rsplit("/", 1)[-1]


def _validate_upload(image_bytes: bytes) -> None:
    if not image_bytes:
        raise HygieneError("Empty upload", "No image was received. Please retake.")
    limit = int(settings.HYGIENE_MAX_UPLOAD_MB * 1024 * 1024)
    if len(image_bytes) > limit:
        raise HygieneError(
            f"Upload {len(image_bytes)} bytes exceeds {limit}",
            f"That image is larger than {settings.HYGIENE_MAX_UPLOAD_MB:g} MB. "
            "Please retake at a smaller size.",
        )


def _store_image(image_bytes: bytes) -> str:
    """Persist a stall photo under a random name.

    Random rather than vendor-supplied: phone filenames collide constantly,
    and a client-controlled path is a traversal risk.
    """
    directory = settings.hygiene_upload_path
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    (directory / filename).write_bytes(image_bytes)
    return f"/uploads/hygiene/{filename}"


def resolve_check(db: Session, check_id: int, user: User) -> HygieneCheck:
    """Load a check, enforcing that the caller may see it.

    Vendors see only their own stalls' checks; reviewers and admins see all.
    404 rather than 403 for someone else's check so the endpoint does not
    confirm that an arbitrary id exists.
    """
    check = db.query(HygieneCheck).filter(HygieneCheck.id == check_id).first()
    if check is None:
        raise HygieneError("Check not found", "That hygiene check was not found.")

    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role in (UserRole.REVIEWER.value, UserRole.ADMIN.value):
        return check

    from app.crud import stall as crud_stall
    from app.crud import vendor as crud_vendor

    if role == UserRole.VENDOR.value:
        vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
        if vendor is not None:
            owned = crud_stall.get_stall(db, check.stall_id)
            if owned is not None and owned.vendor_id == vendor.id:
                return check

    raise HygieneError("Check not found", "That hygiene check was not found.")
