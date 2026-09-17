"""Coverage validation: are all four required views present?

A hygiene assessment from a partial set of photos would produce a number
that looks authoritative and is not -- a stall photographed only from the
front could hide an unswept waste area entirely. Detection therefore runs
only on a complete set, and an incomplete check reports exactly which views
are still needed rather than a generic failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

from app.models.enums import REQUIRED_VIEWS, ViewCategory


@dataclass
class CoverageStatus:
    ok: bool
    present: List[ViewCategory] = field(default_factory=list)
    missing: List[ViewCategory] = field(default_factory=list)
    message: str = ""
    """Vendor-facing, naming the specific views still needed. Empty when
    coverage is complete."""

    next_view: ViewCategory | None = None
    """The view the guided capture flow should ask for next, in the
    canonical order. None when complete."""

    @property
    def progress(self) -> float:
        """Fraction of required views collected, for the progress indicator."""
        return len(self.present) / len(REQUIRED_VIEWS) if REQUIRED_VIEWS else 0.0


def _join_names(views: Sequence[ViewCategory]) -> str:
    """Human-readable list: "the storage area", "A and B", "A, B, and C"."""
    names = [f"the {view.display_name.lower()}" for view in views]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def evaluate_coverage(present_views: Iterable[ViewCategory | str]) -> CoverageStatus:
    """Compare collected views against the required set.

    Accepts raw strings as well as enum members because the view tag arrives
    from an HTTP form field and may not have been coerced yet.
    """
    normalised: set[ViewCategory] = set()
    for raw in present_views:
        if isinstance(raw, ViewCategory):
            normalised.add(raw)
            continue
        try:
            normalised.add(ViewCategory(raw))
        except ValueError:
            # An unrecognised tag is ignored rather than raising: it cannot
            # satisfy a requirement either way, and failing the whole request
            # over it would be worse than reporting it as missing.
            continue

    present = [view for view in REQUIRED_VIEWS if view in normalised]
    missing = [view for view in REQUIRED_VIEWS if view not in normalised]

    if not missing:
        return CoverageStatus(
            ok=True,
            present=present,
            missing=[],
            message="",
            next_view=None,
        )

    return CoverageStatus(
        ok=False,
        present=present,
        missing=missing,
        message=f"Still needed: {_join_names(missing)}.",
        next_view=missing[0],
    )


def describe_missing(missing: Sequence[ViewCategory]) -> str:
    """Exposed separately so callers can build their own phrasing."""
    return _join_names(missing)
