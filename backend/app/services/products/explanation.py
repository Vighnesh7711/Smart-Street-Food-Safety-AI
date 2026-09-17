"""Turn a status decision into the English explanation and advice.

English is always generated first and stored on the product row; translation
happens afterwards in the scan service. Keeping the canonical English in the
database (rather than only the translated text) is what makes the "show
original English" toggle and the reviewer dashboard both trivially correct.
"""

from __future__ import annotations

import logging
from string import Formatter
from typing import Dict, List, Sequence

from app.models.enums import ScanStatus
from app.services.products.matching import IngredientMatch
from app.services.products.status_engine import RuleOutcome, StatusDecision

logger = logging.getLogger(__name__)


class _SafeFormatter(Formatter):
    """Formatter that leaves unknown placeholders intact.

    A seeded template with a typo'd placeholder should degrade to readable
    text ("...at {max_pct}...") rather than raise and fail an entire scan
    over a cosmetic string bug.
    """

    def get_value(self, key, args, kwargs):  # type: ignore[override]
        if isinstance(key, str):
            return kwargs.get(key, f"{{{key}}}")
        return super().get_value(key, args, kwargs)


_formatter = _SafeFormatter()

_EXPLANATIONS: Dict[ScanStatus, str] = {
    ScanStatus.SUITABLE: (
        "No concerns were found among the ingredients we recognised on this "
        "label. This is not a certification -- it means nothing in our "
        "reference list was flagged for this product."
    ),
}


def render_template(template: str, context: Dict[str, str]) -> str:
    """Render an explanation template with named placeholders."""
    try:
        return _formatter.vformat(template, (), context).strip()
    except Exception:  # noqa: BLE001 - a bad template must not fail a scan
        logger.warning("Could not render explanation template: %r", template)
        return template.strip()


def build_explanation(
    decision: StatusDecision,
    all_outcomes: Sequence[RuleOutcome],
    matches: Sequence[IngredientMatch],
) -> str:
    """Build the canonical English explanation for a decision."""
    status = decision.status

    # Statuses that describe a reading problem rather than a finding: the
    # decision already carries the precise, actionable wording.
    if status in (ScanStatus.NEEDS_REVIEW, ScanStatus.INSUFFICIENT_INFORMATION):
        return decision.reason

    if status == ScanStatus.SUITABLE:
        recognised = ", ".join(m.ingredient.canonical_name for m in matches)
        base = _EXPLANATIONS[ScanStatus.SUITABLE]
        if recognised:
            return f"{base}\n\nIngredients recognised: {recognised}."
        return base

    # Mismatch / concern: render the template of each firing rule.
    outcomes = decision.explanation_outcomes or [
        o for o in all_outcomes if o.triggered
    ]

    parts: List[str] = []
    seen: set[str] = set()
    for outcome in outcomes:
        rendered = render_template(outcome.rule.explanation_template, outcome.context)
        if rendered and rendered not in seen:
            seen.add(rendered)
            parts.append(rendered)

    if not parts:
        # A rule fired but produced no template text -- fall back to the
        # decision's own one-line reason so the vendor sees *something*.
        return decision.reason

    return "\n\n".join(parts)


def collect_recommendations(
    all_outcomes: Sequence[RuleOutcome],
    matches: Sequence[IngredientMatch],
) -> List[str]:
    """Advice strings, highest priority first.

    Gathered from the rules that actually fired, plus any ingredient-level
    advice for the ingredients involved. Deliberately does not dump advice
    for every matched ingredient -- a label lists a dozen things and a list
    of a dozen tips is noise, not guidance.
    """
    relevant_ingredient_ids = {
        o.match.ingredient.id for o in all_outcomes if o.triggered
    }
    if not relevant_ingredient_ids:
        return []

    scored: Dict[str, int] = {}
    for outcome in all_outcomes:
        if not outcome.triggered:
            continue
        for recommendation in outcome.rule.recommendations:
            if not recommendation.is_active:
                continue
            # Keep the best (lowest) priority if the same advice appears
            # under two rules.
            existing = scored.get(recommendation.body)
            if existing is None or recommendation.priority < existing:
                scored[recommendation.body] = recommendation.priority

    for match in matches:
        if match.ingredient.id not in relevant_ingredient_ids:
            continue
        for recommendation in getattr(match.ingredient, "recommendations", []) or []:
            if not recommendation.is_active:
                continue
            existing = scored.get(recommendation.body)
            if existing is None or recommendation.priority < existing:
                scored[recommendation.body] = recommendation.priority

    ordered = sorted(scored.items(), key=lambda item: (item[1], item[0]))
    return [body for body, _ in ordered]
