"""The hygiene score formula.

    visual_score    = clamp(100 - sum(finding penalties), 0, 100)
    checklist_score = 100 * (items answered yes / total items)
    final_score     = 0.70 * visual_score + 0.30 * checklist_score

Visual evidence dominates by design. The checklist is self-reported and
unverified, so a vendor must not be able to lift a failing visual score
simply by ticking boxes -- but it still carries enough weight to reward a
stall that genuinely improves the things a camera cannot see (clean water
supply, food stored off the ground).

The formula version is stored on every score row. Scores are never rewritten
in place, so changing the weights or the penalty table creates a new row
with a new version rather than silently restating history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.core.config import settings
from app.models.hygiene_score import CURRENT_FORMULA_VERSION
from app.services.hygiene.indicators import IndicatorFinding


class ScoringConfigError(RuntimeError):
    """The configured weights are not usable."""


@dataclass
class ScoreResult:
    visual_score: float
    checklist_score: Optional[float]
    final_score: float
    breakdown: Dict = field(default_factory=dict)
    weights: Dict = field(default_factory=dict)
    formula_version: str = CURRENT_FORMULA_VERSION


def validate_weights() -> None:
    """Fail loudly at startup rather than producing subtly wrong scores.

    Non-normalised weights would still produce a plausible-looking number,
    which is exactly the kind of bug that survives to production.
    """
    total = settings.HYGIENE_VISUAL_WEIGHT + settings.HYGIENE_CHECKLIST_WEIGHT
    if abs(total - 1.0) > 1e-6:
        raise ScoringConfigError(
            "HYGIENE_VISUAL_WEIGHT + HYGIENE_CHECKLIST_WEIGHT must sum to 1.0 "
            f"(got {settings.HYGIENE_VISUAL_WEIGHT} + "
            f"{settings.HYGIENE_CHECKLIST_WEIGHT} = {total})"
        )
    for name, value in (
        ("HYGIENE_VISUAL_WEIGHT", settings.HYGIENE_VISUAL_WEIGHT),
        ("HYGIENE_CHECKLIST_WEIGHT", settings.HYGIENE_CHECKLIST_WEIGHT),
    ):
        if not 0.0 <= value <= 1.0:
            raise ScoringConfigError(f"{name} must be between 0 and 1 (got {value})")


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def compute_visual_score(
    findings: Sequence[IndicatorFinding],
) -> tuple[float, Dict]:
    """Deduct for each finding, clamped at zero."""
    total_penalty = sum(finding.penalty for finding in findings)
    score = _clamp(100.0 - total_penalty)

    by_view: Dict[str, float] = {}
    for finding in findings:
        by_view[finding.view] = round(
            by_view.get(finding.view, 0.0) + finding.penalty, 2
        )

    breakdown = {
        "total_penalty": round(total_penalty, 2),
        "penalty_by_view": by_view,
        "finding_count": len(findings),
        # Recorded so a clamped-to-zero score can be told apart from one that
        # landed exactly on zero.
        "clamped": total_penalty > 100.0,
        "findings": [finding.to_dict() for finding in findings],
    }
    return round(score, 2), breakdown


def compute_final_score(
    visual_score: float, checklist_score: Optional[float]
) -> float:
    """Blend visual and checklist.

    When the vendor skipped the checklist the visual score is used alone
    rather than substituting a default. Imputing a value would invent an
    answer the vendor never gave, and would make a skipped checklist
    indistinguishable from a completed one in the stored history.
    """
    if checklist_score is None:
        return round(_clamp(visual_score), 2)

    blended = (
        settings.HYGIENE_VISUAL_WEIGHT * visual_score
        + settings.HYGIENE_CHECKLIST_WEIGHT * checklist_score
    )
    return round(_clamp(blended), 2)


def compute_score(
    findings: Sequence[IndicatorFinding],
    checklist_score: Optional[float],
) -> ScoreResult:
    validate_weights()

    visual_score, visual_breakdown = compute_visual_score(findings)
    final_score = compute_final_score(visual_score, checklist_score)

    return ScoreResult(
        visual_score=visual_score,
        checklist_score=checklist_score,
        final_score=final_score,
        breakdown={
            "visual": visual_breakdown,
            "checklist_score": checklist_score,
            "checklist_applied": checklist_score is not None,
        },
        weights={
            "visual": settings.HYGIENE_VISUAL_WEIGHT,
            "checklist": settings.HYGIENE_CHECKLIST_WEIGHT,
        },
    )


#: Inclusive lower bounds for each band, best first. The single source of
#: truth for band boundaries: `score_band` reads it, and
#: `crud/reviewer.py` builds its SQL CASE from it so filtering by band in
#: the database cannot disagree with the band shown in the UI.
BAND_THRESHOLDS: tuple[tuple[str, float], ...] = (
    ("good", 80.0),
    ("fair", 60.0),
    ("poor", 40.0),
)

#: Band for a score below every threshold above.
LOWEST_BAND = "bad"


def score_band(score: float) -> str:
    """Coarse band for UI colour. Deliberately generous at the top: a vendor
    with a mostly clean stall should not see a warning colour."""
    for band, threshold in BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return LOWEST_BAND
