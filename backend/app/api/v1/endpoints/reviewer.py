"""Reviewer dashboard endpoints.

Every route in this module is gated by `require_roles(REVIEWER, ADMIN)`. The
gating is applied via `dependencies=[...]` on the router itself rather than
per-function, so a route added later cannot accidentally be left open -- the
failure mode of per-route decorators is that someone forgets one.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.crud import reviewer as crud_reviewer
from app.db.session import get_db
from app.models.enums import FlagStatus, ReviewSort, UserRole
from app.models.user import User
from app.schemas.reviewer import (
    BandCounts,
    FlagCreate,
    FlagListResponse,
    FlagRead,
    FlagResolve,
    ReviewerSummaryRead,
    VendorDetailRead,
    VendorListResponse,
    VendorRowRead,
    AuditLogListResponse,
    AnalyticsListResponse,
)
from app.services.reviewer import service as reviewer_service
from app.services.reviewer.service import ReviewerError

router = APIRouter(
    # Applied to the whole router. See module docstring.
    dependencies=[Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN))]
)


def _http_error(exc: ReviewerError) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
            if exc.not_found
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        ),
        detail={"detail": exc.user_message},
    )


@router.get(
    "/vendors",
    response_model=VendorListResponse,
    summary="Vendors table (filter, sort, paginate)",
)
def list_vendors(
    search: Optional[str] = Query(
        None, description="Matches stall name or vendor name, case-insensitive."
    ),
    band: Optional[str] = Query(
        None,
        description="good | fair | poor | bad | none. 'none' means never assessed.",
    ),
    flagged: Optional[bool] = Query(None, description="Only stalls with an open flag."),
    has_scan: Optional[bool] = Query(
        None, description="Whether the stall has any label scan at all."
    ),
    sort: ReviewSort = Query(ReviewSort.LAST_ACTIVITY),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> VendorListResponse:
    """One page of the vendors table plus the unpaginated total.

    Filtering, sorting, and pagination all happen in SQL. Doing any of them
    in the browser would be wrong here: filtering a fetched page would
    silently hide a flagged stall beyond the page boundary, and sorting by
    latest score sorts on a derived column that has no client-side value.
    """
    rows, total = crud_reviewer.list_vendor_rows(
        db,
        search=search,
        band=band,
        flagged=flagged,
        has_scan=has_scan,
        sort=sort,
        descending=order == "desc",
        skip=skip,
        limit=limit,
    )
    return VendorListResponse(
        items=[VendorRowRead(**row.__dict__) for row in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/summary",
    response_model=ReviewerSummaryRead,
    summary="Dashboard headline numbers",
)
def read_summary(db: Session = Depends(get_db)) -> ReviewerSummaryRead:
    summary = crud_reviewer.load_summary(db)
    return ReviewerSummaryRead(
        total_stalls=summary.total_stalls,
        assessed_stalls=summary.assessed_stalls,
        flagged_stalls=summary.flagged_stalls,
        average_score=summary.average_score,
        checks_last_7_days=summary.checks_last_7_days,
        bands=BandCounts(**summary.scores),
    )


@router.get(
    "/vendors/{stall_id}",
    response_model=VendorDetailRead,
    summary="Vendor detail: score history, scans, images, flags",
)
def read_vendor_detail(
    stall_id: int, db: Session = Depends(get_db)
) -> VendorDetailRead:
    try:
        stall = reviewer_service.get_stall_or_404(db, stall_id)
    except ReviewerError as exc:
        raise _http_error(exc) from exc
    return reviewer_service.build_detail(db, stall)


@router.get(
    "/flags",
    response_model=FlagListResponse,
    summary="Flagged stalls",
)
def list_flags(
    flag_status: Optional[FlagStatus] = Query(
        None,
        alias="status",
        description="Defaults to open flags only.",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> FlagListResponse:
    """Open flags by default. `status=resolved` reveals history; omitting the
    parameter entirely means "open", not "all"."""
    effective = flag_status or FlagStatus.OPEN
    items, total = reviewer_service.list_flags(
        db, status=effective, skip=skip, limit=limit
    )
    return FlagListResponse(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "/vendors/{stall_id}/flags",
    response_model=FlagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Flag a stall for follow-up",
)
def create_flag(
    stall_id: int,
    payload: FlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.REVIEWER, UserRole.ADMIN)
    ),
) -> FlagRead:
    """Raise a flag. The reason is required -- see FlagCreate."""
    try:
        stall = reviewer_service.get_stall_or_404(db, stall_id)
    except ReviewerError as exc:
        raise _http_error(exc) from exc

    flag = reviewer_service.create_flag(
        db, stall=stall, user=current_user, reason=payload.reason
    )
    flags = reviewer_service.open_flags_for_stall(db, stall_id)
    return next((f for f in flags if f.id == flag.id), flags[0])


@router.post(
    "/flags/{flag_id}/resolve",
    response_model=FlagRead,
    summary="Resolve a flag",
)
def resolve_flag(
    flag_id: int,
    payload: FlagResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.REVIEWER, UserRole.ADMIN)
    ),
) -> FlagRead:
    flag = reviewer_service.get_flag(db, flag_id)
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "That flag was not found."},
        )
    try:
        reviewer_service.resolve_flag(
            db, flag=flag, user=current_user, note=payload.note
        )
    except ReviewerError as exc:
        raise _http_error(exc) from exc
    return FlagRead(
        id=flag.id,
        stall_id=flag.stall_id,
        stall_name=flag.stall.name if flag.stall else None,
        reason=flag.reason,
        status=FlagStatus(flag.status),
        created_by_name=(
            flag.created_by.full_name if flag.created_by else None
        ),
        created_at=flag.created_at,
        resolved_by_name=(
            flag.resolved_by.full_name if flag.resolved_by else None
        ),
        resolved_at=flag.resolved_at,
        resolution_note=flag.resolution_note,
    )


@router.get(
    "/audit",
    response_model=AuditLogListResponse,
    summary="Reviewer audit trail",
)
def list_audit_logs(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    from app.models.audit_log import AuditLog
    total = db.query(AuditLog).count()
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    
    items = []
    for log in logs:
        items.append(
            schemas.reviewer.AuditLogRead(
                id=log.id,
                action=log.action,
                actor_id=log.actor_id,
                actor_name=log.actor.full_name if log.actor else None,
                target_type=log.target_type,
                target_id=log.target_id,
                details=log.details,
                created_at=log.created_at,
            )
        )
    return schemas.reviewer.AuditLogListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/analytics",
    response_model=AnalyticsListResponse,
    summary="Reviewer analytics aggregates",
)
def get_analytics(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    from app.models.analytics import AnalyticsAggregate
    from datetime import date, timedelta
    
    start_date = date.today() - timedelta(days=days)
    records = db.query(AnalyticsAggregate).filter(
        AnalyticsAggregate.date >= start_date
    ).order_by(AnalyticsAggregate.date.asc()).all()
    
    items = []
    for r in records:
        items.append(
            schemas.reviewer.AnalyticsAggregateRead(
                date=r.date,
                total_stalls=r.total_stalls,
                assessed_stalls=r.assessed_stalls,
                flagged_stalls=r.flagged_stalls,
                average_score=r.average_score,
                scans_performed=r.scans_performed,
                flags_created=r.flags_created,
                flags_resolved=r.flags_resolved,
                checks_performed=r.checks_performed,
            )
        )
    return schemas.reviewer.AnalyticsListResponse(items=items)
