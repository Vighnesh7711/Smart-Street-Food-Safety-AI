"""Hygiene check endpoints: guided capture, scoring, and history."""

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, require_roles
from app.api.v1.endpoints.stalls import get_stall_for_reader
from app.core.config import settings
from app.core.constants import DISCLAIMER as _DISCLAIMER
from app.crud import hygiene as crud_hygiene
from app.crud import stall as crud_stall
from app.crud import vendor as crud_vendor
from app.db.session import get_db
from app.models.enums import REQUIRED_VIEWS, CheckStatus, UserRole, ViewCategory
from app.models.hygiene_check import HygieneCheck
from app.models.user import User
from app.schemas.hygiene import (
    ChecklistAnswerRow,
    ChecklistItemRead,
    ChecklistSubmit,
    CoverageRead,
    HygieneCheckRead,
    HygieneCheckSummary,
    HygieneConfigRead,
    HygieneImageRead,
    HygieneScoreRead,
    IndicatorCatalogRead,
    IndicatorFindingRead,
)
from app.services.hygiene import checklist as checklist_service
from app.services.hygiene import coverage as coverage_service
from app.services.hygiene import hygiene_service, scoring
from app.services.hygiene.hygiene_service import HygieneError

router = APIRouter()

_MAX_UPLOAD_BYTES = int(settings.HYGIENE_MAX_UPLOAD_MB * 1024 * 1024)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _coverage_of(check: HygieneCheck) -> CoverageRead:
    views = [image.view_category for image in check.images] if check.images else []
    status_ = coverage_service.evaluate_coverage(views)
    return CoverageRead(
        ok=status_.ok,
        present=status_.present,
        missing=status_.missing,
        message=status_.message,
        next_view=status_.next_view,
        progress=round(status_.progress, 3),
    )


def _image_read(image) -> HygieneImageRead:
    quality = image.quality or {}
    return HygieneImageRead(
        id=image.id,
        view_category=ViewCategory(image.view_category),
        view_display_name=ViewCategory(image.view_category).display_name,
        image_url=image.image_path,
        quality_ok=bool(quality.get("ok", True)),
        quality_issues=list(quality.get("issues") or []),
        created_at=image.created_at,
    )


def _score_read(score) -> Optional[HygieneScoreRead]:
    if score is None:
        return None
    return HygieneScoreRead(
        visual_score=score.visual_score,
        checklist_score=score.checklist_score,
        final_score=score.final_score,
        band=scoring.score_band(score.final_score),
        formula_version=score.formula_version,
        weights=score.weights or {},
        computed_at=score.computed_at,
    )


def _check_read(db: Session, check: HygieneCheck) -> HygieneCheckRead:
    catalog = {row.code: row for row in hygiene_service.load_indicator_catalog(db)}
    score = check.score or crud_hygiene.latest_score_for(db, check.id)

    # The stored summary is compact (it is the GIN-indexed filter column),
    # so display names are resolved from the catalog here rather than being
    # duplicated into every stored row.
    findings: List[IndicatorFindingRead] = []
    for entry in check.indicators_found or []:
        code = entry.get("code")
        row = catalog.get(code)
        findings.append(
            IndicatorFindingRead(
                code=code,
                display_name=(
                    row.display_name if row else str(code).replace("_", " ").title()
                ),
                view=entry.get("view", ""),
                severity=(row.default_severity if row else "moderate"),
                penalty=float(entry.get("penalty", 0.0)),
                confidence=float(entry.get("confidence", 0.0)),
                detection_count=int(entry.get("detection_count", 1)),
                raw_labels=list(entry.get("raw_labels") or []),
            )
        )

    return HygieneCheckRead(
        id=check.id,
        stall_id=check.stall_id,
        status=CheckStatus(check.status),
        coverage=_coverage_of(check),
        images=[_image_read(image) for image in check.images],
        score=_score_read(score),
        indicators_found=findings,
        checklist=[
            ChecklistAnswerRow(**row)
            for row in checklist_service.describe_checklist(check.checklist)
        ],
        created_at=check.created_at,
        scored_at=check.scored_at,
        disclaimer=_DISCLAIMER,
    )


def _summary(db: Session, check: HygieneCheck) -> HygieneCheckSummary:
    score = check.score or crud_hygiene.latest_score_for(db, check.id)
    thumbnail = next(
        (i.image_path for i in check.images if i.view_category == ViewCategory.OVERALL.value),
        check.images[0].image_path if check.images else None,
    )
    return HygieneCheckSummary(
        id=check.id,
        stall_id=check.stall_id,
        status=CheckStatus(check.status),
        final_score=score.final_score if score else None,
        band=scoring.score_band(score.final_score) if score else None,
        indicator_count=len(check.indicators_found or []),
        coverage_ok=bool(check.coverage_ok),
        missing_views=[ViewCategory(v) for v in (check.missing_views or []) if v in {x.value for x in ViewCategory}],
        thumbnail_url=thumbnail,
        created_at=check.created_at,
        scored_at=check.scored_at,
    )


def _stall_ids_for(db: Session, user: User) -> Optional[List[int]]:
    """Stalls the caller may see, or None for unrestricted roles."""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role in (UserRole.REVIEWER.value, UserRole.ADMIN.value):
        return None
    if role == UserRole.VENDOR.value:
        vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
        if vendor is None:
            return []
        return [s.id for s in crud_stall.list_stalls_by_vendor(db, vendor_id=vendor.id)]
    return []


def _http_error(exc: HygieneError) -> HTTPException:
    """Map a service error to a response the client can act on.

    A missing check is a 404; everything else is a 422 (the vendor's input
    or photo was rejected) or a 503 (the service could not do its job).
    """
    if "not found" in exc.user_message.lower():
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": exc.user_message, "retryable": False},
        )
    code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if exc.retryable
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(
        status_code=code,
        detail={"detail": exc.user_message, "retryable": exc.retryable},
    )


# ---------------------------------------------------------------------------
# Config / catalog
# ---------------------------------------------------------------------------


@router.get("/config", response_model=HygieneConfigRead, summary="Capture flow config")
def read_config(
    _: User = Depends(get_current_active_user),
) -> HygieneConfigRead:
    """Everything the mobile capture flow needs to render itself.

    Served from the server rather than hardcoded in the app so adding a view
    or a checklist item does not require a frontend release.
    """
    return HygieneConfigRead(
        required_views=[
            {
                "value": view.value,
                "display_name": view.display_name,
                "prompt": view.prompt,
                "hint": view.hint,
                "step": index + 1,
            }
            for index, view in enumerate(REQUIRED_VIEWS)
        ],
        checklist_items=[
            ChecklistItemRead(**item)
            for item in hygiene_service.checklist_catalog()
        ],
        disclaimer=_DISCLAIMER,
    )


@router.get(
    "/indicators",
    response_model=List[IndicatorCatalogRead],
    summary="Indicator catalog (reviewer/admin only)",
)
def list_indicators(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN)),
) -> List[IndicatorCatalogRead]:
    return [
        IndicatorCatalogRead(
            code=row.code,
            display_name=row.display_name,
            description=row.description,
            default_severity=row.default_severity,
            view_penalties=row.view_penalties or {},
        )
        for row in hygiene_service.load_indicator_catalog(db)
    ]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


@router.post(
    "/checks",
    response_model=HygieneCheckRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) a hygiene check",
)
def create_check(
    stall_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> HygieneCheckRead:
    """Open a draft check for a stall.

    Returns the vendor's existing unfinished check for that stall if one
    exists, so abandoning the flow and reopening it does not litter the
    history with empty drafts.
    """
    stall = get_stall_for_reader(db, stall_id, current_user)
    check = hygiene_service.create_check(db, stall=stall, user=current_user)
    return _check_read(db, check)


@router.get(
    "/checks",
    response_model=List[HygieneCheckSummary],
    summary="Check history (vendor: own stalls; reviewer: all)",
)
def list_checks(
    db: Session = Depends(get_db),
    stall_id: Optional[int] = Query(None),
    include_unfinished: bool = Query(False),
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
) -> List[HygieneCheckSummary]:
    stall_ids = _stall_ids_for(db, current_user)

    if stall_id is not None:
        # Confirm the caller may see this stall rather than trusting the
        # filter alone.
        get_stall_for_reader(db, stall_id, current_user)
        stall_ids = [stall_id]

    checks = crud_hygiene.list_checks(
        db,
        stall_ids=stall_ids,
        include_unfinished=include_unfinished,
        skip=skip,
        limit=limit,
    )
    return [_summary(db, check) for check in checks]


@router.get(
    "/checks/{check_id}",
    response_model=HygieneCheckRead,
    summary="Check detail",
)
def read_check(
    check_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> HygieneCheckRead:
    try:
        check = hygiene_service.resolve_check(db, check_id, current_user)
    except HygieneError as exc:
        raise _http_error(exc) from exc
    return _check_read(db, check)


@router.post(
    "/checks/{check_id}/images",
    response_model=HygieneCheckRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one view photo",
)
def upload_view_image(
    check_id: int,
    view_category: ViewCategory = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> HygieneCheckRead:
    """Attach a photo for one of the four required views.

    Rejects a photo that duplicates another view in the same check, and
    returns the updated coverage so the client knows which view to ask for
    next.
    """
    try:
        check = hygiene_service.resolve_check(db, check_id, current_user)
    except HygieneError as exc:
        raise _http_error(exc) from exc

    image_bytes = file.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "detail": "That image is too large. Please retake at a smaller size.",
                "retryable": False,
            },
        )

    try:
        hygiene_service.add_view_image(
            db,
            check=check,
            view=view_category,
            image_bytes=image_bytes,
        )
    except HygieneError as exc:
        raise _http_error(exc) from exc

    # Re-read so the response reflects the committed state.
    refreshed = crud_hygiene.get_check(db, check_id)
    return _check_read(db, refreshed or check)

from pydantic import BaseModel

class HygieneImageJSON(BaseModel):
    view_category: ViewCategory
    file_base64: str

@router.post(
    "/checks/{check_id}/images-json",
    response_model=HygieneCheckRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one view photo (JSON Base64)",
)
def upload_view_image_json(
    check_id: int,
    payload: HygieneImageJSON,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> HygieneCheckRead:
    try:
        check = hygiene_service.resolve_check(db, check_id, current_user)
    except HygieneError as exc:
        raise _http_error(exc) from exc

    import base64
    data = payload.file_base64
    if "," in data:
        data = data.split(",", 1)[1]
    
    try:
        image_bytes = base64.b64decode(data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid base64 image data"
        )
        
    if len(image_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "detail": "That image is too large. Please retake at a smaller size.",
                "retryable": False,
            },
        )

    try:
        hygiene_service.add_view_image(
            db,
            check=check,
            view=payload.view_category,
            image_bytes=image_bytes,
        )
    except HygieneError as exc:
        raise _http_error(exc) from exc

    refreshed = crud_hygiene.get_check(db, check_id)
    return _check_read(db, refreshed or check)


@router.post(
    "/checks/{check_id}/checklist",
    response_model=HygieneCheckRead,
    summary="Submit self-declared checklist answers",
)
def submit_checklist(
    check_id: int,
    payload: ChecklistSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> HygieneCheckRead:
    try:
        check = hygiene_service.resolve_check(db, check_id, current_user)
        hygiene_service.submit_checklist(db, check=check, answers=payload.answers)
    except HygieneError as exc:
        raise _http_error(exc) from exc
    return _check_read(db, check)


@router.post(
    "/checks/{check_id}/complete",
    response_model=HygieneCheckRead,
    summary="Score the check once all four views are present",
)
def complete_check(
    check_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> HygieneCheckRead:
    """Run indicator detection across the four views and compute the score.

    Fails with a message naming the missing views if coverage is incomplete
    -- the spec's requirement that the vendor be told exactly which view is
    still needed.
    """
    try:
        check = hygiene_service.resolve_check(db, check_id, current_user)
        hygiene_service.complete_check(db, check=check)
    except HygieneError as exc:
        raise _http_error(exc) from exc

    refreshed = crud_hygiene.get_check(db, check_id)
    return _check_read(db, refreshed or check)
