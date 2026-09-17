"""Idempotent seed for the hygiene indicator catalog.

Run with:

    python -m app.seeds.hygiene_seed

Safe to re-run; rows are matched on `code` and updated in place, so
`hygiene_checks.indicators_found` references (which store the code) keep
resolving after a re-seed.

The checklist items are pure data with no table of their own -- they are
scored from `SEED_CHECKLIST_ITEMS` directly and only the vendor's answers
are persisted. Adding an item is therefore a code change, which is
appropriate for something the scoring formula iterates over.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import RiskLevel, ViewCategory
from app.models.hygiene_indicator import HygieneIndicator
from app.seeds.hygiene_seed_data import SEED_CHECKLIST_ITEMS, SEED_INDICATORS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed.hygiene")

_VALID_VIEWS = {v.value for v in ViewCategory}
_VALID_SEVERITIES = {s.value for s in RiskLevel}


def _validate() -> list[str]:
    """Catch seed mistakes before touching the database.

    A penalty keyed on a misspelled view name would simply never match, and
    the indicator would silently never fire -- a failure that produces no
    error and no log line.
    """
    problems: list[str] = []
    seen: set[str] = set()

    for item in SEED_INDICATORS:
        code = item.code.value
        if code in seen:
            problems.append(f"duplicate indicator code: {code}")
        seen.add(code)

        if item.severity.value not in _VALID_SEVERITIES:
            problems.append(f"{code}: invalid severity {item.severity.value!r}")

        if not item.view_penalties:
            problems.append(f"{code}: no view_penalties -- it could never fire")

        for view, penalty in item.view_penalties.items():
            if view not in _VALID_VIEWS:
                problems.append(f"{code}: unknown view {view!r} in view_penalties")
            if penalty < 0:
                problems.append(f"{code}: negative penalty for {view!r}")
            if penalty > 100:
                problems.append(f"{code}: penalty {penalty} for {view!r} exceeds 100")

        if not item.cv_labels:
            problems.append(f"{code}: no cv_labels -- nothing can ever detect it")

    checklist_codes = [item.code for item in SEED_CHECKLIST_ITEMS]
    if len(checklist_codes) != len(set(checklist_codes)):
        problems.append("duplicate checklist item codes")

    return problems


def _apply_indicator(db: Session, seed) -> bool:
    """Create or update one indicator. Returns True if it was created."""
    indicator = (
        db.query(HygieneIndicator)
        .filter(HygieneIndicator.code == seed.code.value)
        .first()
    )
    created = indicator is None
    if created:
        indicator = HygieneIndicator(code=seed.code.value)
        db.add(indicator)

    # All NOT NULL columns assigned before the first flush, or the INSERT
    # goes out with them unset -- the bug that broke the Phase 2 seed.
    indicator.display_name = seed.display_name
    indicator.description = seed.description
    indicator.default_severity = seed.severity.value
    indicator.view_penalties = dict(seed.view_penalties)
    indicator.cv_labels = list(seed.cv_labels)
    indicator.is_active = True
    db.flush()
    return created


def seed(db: Session) -> tuple[int, int]:
    created = updated = 0
    for item in SEED_INDICATORS:
        if _apply_indicator(db, item):
            created += 1
        else:
            updated += 1
    db.commit()
    return created, updated


def main() -> int:
    problems = _validate()
    if problems:
        logger.error("Hygiene seed data has %d problem(s):", len(problems))
        for problem in problems:
            logger.error("  - %s", problem)
        return 1

    db = SessionLocal()
    try:
        created, updated = seed(db)
    finally:
        db.close()

    logger.info(
        "Seeded %d hygiene indicators (%d created, %d updated) and %d checklist items.",
        len(SEED_INDICATORS),
        created,
        updated,
        len(SEED_CHECKLIST_ITEMS),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
