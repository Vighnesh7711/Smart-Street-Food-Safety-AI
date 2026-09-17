"""Self-declared checklist scoring.

Worth 30% of the final score, deliberately. These are unverified statements
by the vendor, so they must not be able to carry a failing visual score --
but they cover real compliance items a photograph cannot show (is there
clean water? is food stored off the ground?).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.seeds.hygiene_seed_data import CHECKLIST_POSITIVE, SEED_CHECKLIST_ITEMS

#: code -> whether a "yes" answer is the good one.
POSITIVE_ANSWERS = CHECKLIST_POSITIVE

TOTAL_ITEMS = len(SEED_CHECKLIST_ITEMS)


def item_codes() -> List[str]:
    return [item.code for item in SEED_CHECKLIST_ITEMS]


def score_checklist(answers: Optional[Dict[str, bool]]) -> Tuple[Optional[float], Dict]:
    """Score the checklist answers out of 100.

    Returns (None, breakdown) when nothing was answered, so the caller can
    fall back to the visual score rather than imputing compliance the vendor
    never claimed.

    Unanswered items are counted as *not* satisfied. Treating them as
    satisfied would mean a vendor could score full marks by answering
    nothing, and treating them as a separate category would need a third
    state the mobile UI does not have.
    """
    if not answers:
        return None, {
            "answered": 0,
            "satisfied": 0,
            "total": TOTAL_ITEMS,
            "ignored_codes": [],
            "skipped": True,
        }

    satisfied = 0
    answered = 0
    ignored: List[str] = []
    per_item: Dict[str, bool] = {}

    for code in item_codes():
        if code not in answers:
            per_item[code] = False
            continue
        answered += 1
        value = bool(answers[code])
        # A future negatively-phrased item ("I reuse frying oil") would be
        # inverted via POSITIVE_ANSWERS rather than silently scoring wrong.
        counts_as_satisfied = value if POSITIVE_ANSWERS.get(code, True) else not value
        per_item[code] = counts_as_satisfied
        if counts_as_satisfied:
            satisfied += 1

    for code in answers:
        if code not in POSITIVE_ANSWERS:
            ignored.append(code)

    score = (satisfied / TOTAL_ITEMS) * 100.0 if TOTAL_ITEMS else 0.0

    return round(score, 2), {
        "answered": answered,
        "satisfied": satisfied,
        "total": TOTAL_ITEMS,
        "per_item": per_item,
        "ignored_codes": sorted(ignored),
        "skipped": False,
    }


def describe_checklist(answers: Optional[Dict[str, bool]]) -> List[dict]:
    """Item-by-item view for the results screen: what was asked, what was
    answered, and what it cost."""
    if not answers:
        return []

    rows = []
    for item in SEED_CHECKLIST_ITEMS:
        answered = item.code in answers
        value = bool(answers.get(item.code, False))
        satisfied = (
            value if POSITIVE_ANSWERS.get(item.code, True) else not value
        ) if answered else False
        rows.append(
            {
                "code": item.code,
                "label": item.label,
                "help_text": item.help_text,
                "answered": answered,
                "answer": value if answered else None,
                "satisfied": satisfied,
            }
        )
    return rows
