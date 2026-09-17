"""Aggregate queries behind the reviewer dashboard.

THE N+1 PROBLEM THIS MODULE EXISTS TO AVOID
-------------------------------------------
The vendors table shows, per stall: the latest hygiene score, the latest
label-scan status, and the last activity date. Those live in three different
tables, so the obvious implementation issues three queries per row -- 600
queries for a 200-row page. On seed data that is invisible; on a real
register it is the difference between a dashboard and a timeout.

Everything the table needs is therefore computed in **one** statement, using
correlated scalar subqueries, and the whole thing is wrapped in a subquery so
the derived columns can be filtered and sorted on directly. That wrapping is
what makes "sort by latest hygiene score" possible at all: an ORDER BY cannot
reference a select-list alias in the same level in PostgreSQL.

`tests/test_reviewer_queries.py` asserts the query count, because this is a
property that regresses silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.enums import FlagStatus, ReviewSort
from app.models.flag import Flag
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_score import HygieneScore
from app.models.product import Product
from app.models.stall import Stall
from app.models.user import User
from app.models.vendor import Vendor
from app.services.hygiene.scoring import BAND_THRESHOLDS, LOWEST_BAND


@dataclass
class VendorRow:
    """One row of the vendors table -- a stall, with its derived columns."""

    stall_id: int
    stall_name: str
    food_category: Optional[str]
    vendor_name: Optional[str]
    vendor_id: int
    latest_score: Optional[float]
    latest_score_at: Optional[object]
    band: Optional[str]
    latest_scan_status: Optional[str]
    latest_scan_at: Optional[object]
    last_activity_at: Optional[object]
    has_open_flag: bool
    open_flag_count: int
    created_at: Optional[object]


def _latest_score_subquery(column):
    """Most recent hygiene score for the enclosing stall.

    Ordered by computed_at then id so two scores written in the same
    transaction still have a deterministic "latest".
    """
    return (
        sa.select(column)
        .select_from(HygieneScore)
        .join(HygieneCheck, HygieneCheck.id == HygieneScore.hygiene_check_id)
        .where(HygieneCheck.stall_id == Stall.id)
        .order_by(HygieneScore.computed_at.desc(), HygieneScore.id.desc())
        .limit(1)
        .correlate(Stall)
        .scalar_subquery()
    )


def _latest_scan_subquery(column):
    return (
        sa.select(column)
        .select_from(Product)
        .where(Product.stall_id == Stall.id)
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(1)
        .correlate(Stall)
        .scalar_subquery()
    )


def _seven_days_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=7)


def _band_case(score_column):
    """SQL equivalent of services.hygiene.scoring.score_band.

    Built from BAND_THRESHOLDS rather than hardcoded numbers, so a band
    boundary change cannot leave the reviewer's filter disagreeing with the
    band the dashboard displays.

    The explicit NULL branch is load-bearing. Without it, a stall that has
    never been assessed falls through every comparison (NULL >= 80 is NULL,
    not false) and lands on the `else_` band -- so an unassessed stall would
    display as the WORST possible band and sort to the top of a worst-first
    list. "No data" is not "bad data".
    """
    whens = [(score_column >= threshold, name) for name, threshold in BAND_THRESHOLDS]
    return sa.case(
        (score_column.is_(None), None),
        *whens,
        else_=LOWEST_BAND,
    )


def _base_query():
    """The single statement: one row per stall, with derived columns."""
    latest_score = _latest_score_subquery(HygieneScore.final_score).label(
        "latest_score"
    )
    latest_score_at = _latest_score_subquery(HygieneScore.computed_at).label(
        "latest_score_at"
    )
    latest_scan_status = _latest_scan_subquery(Product.status).label(
        "latest_scan_status"
    )
    latest_scan_at = _latest_scan_subquery(Product.created_at).label("latest_scan_at")

    open_flag_count = (
        sa.select(sa.func.count(Flag.id))
        .where(Flag.stall_id == Stall.id, Flag.status == FlagStatus.OPEN.value)
        .correlate(Stall)
        .scalar_subquery()
    )

    # "Last activity" is the most recent thing that happened to this stall.
    #
    # Written as a CASE rather than GREATEST(): GREATEST is PostgreSQL-only
    # (SQLite spells the scalar form MAX), and this query has to run on both.
    # Each side is COALESCEd against the stall's own creation date, because a
    # stall with no checks and no scans is still not "never active" -- it was
    # registered.
    score_or_created = sa.func.coalesce(latest_score_at, Stall.created_at)
    scan_or_created = sa.func.coalesce(latest_scan_at, Stall.created_at)
    last_activity = sa.case(
        (score_or_created >= scan_or_created, score_or_created),
        else_=scan_or_created,
    ).label("last_activity_at")

    return (
        sa.select(
            Stall.id.label("stall_id"),
            Stall.name.label("stall_name"),
            Stall.food_category.label("food_category"),
            Stall.created_at.label("created_at"),
            Vendor.id.label("vendor_id"),
            User.full_name.label("vendor_name"),
            latest_score,
            latest_score_at,
            _band_case(latest_score).label("band"),
            latest_scan_status,
            latest_scan_at,
            last_activity,
            open_flag_count.label("open_flag_count"),
        )
        .select_from(Stall)
        .join(Vendor, Vendor.id == Stall.vendor_id)
        .outerjoin(User, User.id == Vendor.user_id)
    )


def _is_known_band(band: str) -> bool:
    return band == "none" or band == LOWEST_BAND or band in dict(BAND_THRESHOLDS)


def list_vendor_rows(
    db: Session,
    *,
    search: Optional[str] = None,
    band: Optional[str] = None,
    flagged: Optional[bool] = None,
    has_scan: Optional[bool] = None,
    sort: ReviewSort = ReviewSort.LAST_ACTIVITY,
    descending: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[VendorRow], int]:
    """One page of the vendors table, plus the unpaginated total.

    The total is returned separately because the client shows "showing 1-50
    of 240": a paginated table without a total leaves a reviewer unable to
    tell whether they are looking at 12 stalls or 1,200.
    """
    inner = _base_query().subquery()

    conditions = []

    if search:
        # ILIKE on both the stall and the vendor: a reviewer looking for
        # "Ramesh" should find his stall whether they know its name or his.
        pattern = f"%{search.strip()}%"
        conditions.append(
            sa.or_(
                inner.c.stall_name.ilike(pattern),
                inner.c.vendor_name.ilike(pattern),
            )
        )

    if band:
        # Filtered on the computed band column itself, rather than
        # re-deriving score ranges here. One expression decides what band a
        # stall is in, so the filter can never disagree with the value the
        # table displays.
        if not _is_known_band(band):
            # Unknown band name: match nothing rather than silently ignoring
            # the filter, which would show every stall to a reviewer who
            # asked for a specific band.
            conditions.append(sa.false())
        elif band == "none":
            conditions.append(inner.c.band.is_(None))
        else:
            conditions.append(inner.c.band == band)

    if flagged is not None:
        conditions.append(
            (inner.c.open_flag_count > 0) if flagged else (inner.c.open_flag_count == 0)
        )

    if has_scan is not None:
        conditions.append(
            inner.c.latest_scan_status.isnot(None)
            if has_scan
            else inner.c.latest_scan_status.is_(None)
        )

    total = db.execute(
        sa.select(sa.func.count()).select_from(inner).where(*conditions)
    ).scalar_one()

    sort_columns = {
        ReviewSort.STALL_NAME: inner.c.stall_name,
        ReviewSort.HYGIENE: inner.c.latest_score,
        ReviewSort.LAST_SCAN: inner.c.latest_scan_at,
        ReviewSort.LAST_ACTIVITY: inner.c.last_activity_at,
        ReviewSort.CREATED_AT: inner.c.created_at,
    }
    column = sort_columns.get(sort, inner.c.last_activity_at)

    # NULLS LAST in both directions: a stall with no assessment should sit at
    # the bottom of a score-sorted list whichever way it is sorted, not
    # masquerade as the worst performer.
    ordering = column.desc().nullslast() if descending else column.asc().nullslast()

    rows = db.execute(
        sa.select(inner)
        .where(*conditions)
        # Tie-break on id so pagination is stable: without it, two stalls with
        # the same score can swap places between pages and one gets skipped.
        .order_by(ordering, inner.c.stall_id.asc())
        .offset(skip)
        .limit(limit)
    ).mappings()

    return [_row_from_mapping(row) for row in rows], int(total)


def _row_from_mapping(row) -> VendorRow:
    return VendorRow(
        stall_id=row["stall_id"],
        stall_name=row["stall_name"],
        food_category=row["food_category"],
        vendor_id=row["vendor_id"],
        vendor_name=row["vendor_name"],
        latest_score=row["latest_score"],
        latest_score_at=row["latest_score_at"],
        band=row["band"],
        latest_scan_status=row["latest_scan_status"],
        latest_scan_at=row["latest_scan_at"],
        last_activity_at=row["last_activity_at"],
        has_open_flag=bool(row["open_flag_count"]),
        open_flag_count=int(row["open_flag_count"] or 0),
        created_at=row["created_at"],
    )


@dataclass
class ReviewerSummary:
    total_stalls: int
    assessed_stalls: int
    flagged_stalls: int
    average_score: Optional[float]
    checks_last_7_days: int
    scores: dict


def load_summary(db: Session) -> ReviewerSummary:
    """Headline numbers for the dashboard's KPI row.

    Kept to two queries (stall aggregates, then check counts) rather than one
    per figure.
    """
    inner = _base_query().subquery()

    row = db.execute(
        sa.select(
            sa.func.count().label("total"),
            sa.func.count(inner.c.latest_score).label("assessed"),
            sa.func.sum(
                sa.case((inner.c.open_flag_count > 0, 1), else_=0)
            ).label("flagged"),
            sa.func.avg(inner.c.latest_score).label("average"),
        ).select_from(inner)
    ).one()

    recent = db.execute(
        sa.select(sa.func.count(HygieneScore.id))
        .select_from(HygieneScore)
        .join(HygieneCheck, HygieneCheck.id == HygieneScore.hygiene_check_id)
        # Cutoff computed in Python, not as SQL `now() - INTERVAL '7 days'`:
        # the INTERVAL literal is PostgreSQL-only and this runs on SQLite too.
        .where(HygieneScore.computed_at >= _seven_days_ago())
    ).scalar_one()

    # Per-band counts, so the KPI row can show a distribution rather than
    # only an average that hides a bimodal register.
    band_counts = {name: 0 for name, _ in BAND_THRESHOLDS}
    band_counts[LOWEST_BAND] = 0
    band_counts["none"] = 0
    for band_name, count in db.execute(
        sa.select(inner.c.band, sa.func.count()).select_from(inner).group_by(inner.c.band)
    ).all():
        band_counts[band_name or "none"] = int(count)

    return ReviewerSummary(
        total_stalls=int(row.total or 0),
        assessed_stalls=int(row.assessed or 0),
        flagged_stalls=int(row.flagged or 0),
        average_score=float(row.average) if row.average is not None else None,
        checks_last_7_days=int(recent or 0),
        scores=band_counts,
    )


def latest_open_flags_for_stalls(
    db: Session, stall_ids: Sequence[int]
) -> dict[int, Flag]:
    """Open flags for a page of stalls, in one query.

    Used to show flag reasons inline on the table and detail page without
    issuing a query per row.
    """
    if not stall_ids:
        return {}
    flags = (
        db.query(Flag)
        .filter(Flag.stall_id.in_(list(stall_ids)), Flag.status == FlagStatus.OPEN.value)
        .order_by(Flag.created_at.desc(), Flag.id.desc())
        .all()
    )
    first_by_stall: dict[int, Flag] = {}
    for flag in flags:
        first_by_stall.setdefault(flag.stall_id, flag)
    return first_by_stall
