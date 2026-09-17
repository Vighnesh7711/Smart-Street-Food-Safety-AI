"""Turn raw CV detections into scored hygiene findings.

The whole point of this layer is `view_penalties`: the same detection means
different things in different views. Waste inside the waste area is a
functioning bin; the same waste on the preparation surface is a
contamination hazard. Scoring every detection identically would penalise a
vendor for owning a bin, which is the fastest way to make the score
distrustworthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from app.integrations.cv_client import Detection
from app.models.enums import RiskLevel, ViewCategory

#: Severity -> multiplier applied to a view's penalty.
#:
#: Capped at 1.0 rather than scaling upward: a high-severity indicator
#: already carries the largest configured penalty, and multiplying past 1.0
#: would make the configured numbers stop meaning what they say.
SEVERITY_MULTIPLIER: Dict[str, float] = {
    RiskLevel.LOW.value: 0.6,
    RiskLevel.MODERATE.value: 0.8,
    RiskLevel.HIGH.value: 1.0,
}


@dataclass
class IndicatorFinding:
    code: str
    display_name: str
    view: str
    severity: str
    penalty: float
    confidence: float
    """Highest confidence seen for this indicator in this view."""

    detection_count: int = 1
    raw_labels: List[str] = field(default_factory=list)
    source: str = "heuristic"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "display_name": self.display_name,
            "view": self.view,
            "severity": self.severity,
            "penalty": round(self.penalty, 2),
            "confidence": round(self.confidence, 4),
            "detection_count": self.detection_count,
            "raw_labels": self.raw_labels,
            "source": self.source,
        }


def severity_multiplier(severity: str) -> float:
    return SEVERITY_MULTIPLIER.get(severity, SEVERITY_MULTIPLIER[RiskLevel.MODERATE.value])


def build_findings(
    detections_by_view: Dict[str, Sequence[Detection]],
    indicator_rows: Iterable,
) -> List[IndicatorFinding]:
    """Collapse detections into one finding per (indicator, view).

    Multiple detections of the *same* indicator in the *same* view are
    merged and scored once, using the highest confidence. Without this a
    cluttered photo producing fifty "cup" detections would multiply the
    penalty fifty times and drive any stall to zero -- the score would
    measure how busy the photo was rather than how dirty the stall is.
    """
    catalog = {row.code: row for row in indicator_rows}
    findings: List[IndicatorFinding] = []

    for view_value, detections in detections_by_view.items():
        # indicator code -> merged detection
        merged: Dict[str, Detection] = {}
        for detection in detections:
            existing = merged.get(detection.label)
            if existing is None or detection.confidence > existing.confidence:
                merged[detection.label] = detection

        for code, detection in merged.items():
            row = catalog.get(code)
            if row is None or not row.is_active:
                # Unknown indicator: a provider emitted a label the catalog
                # does not know. Skipped rather than guessed at, so a model
                # swap cannot silently change scores via unmapped labels.
                continue

            penalties = row.view_penalties or {}
            if view_value not in penalties:
                # Absent from the map means the indicator does not apply in
                # this view at all -- distinct from a penalty of 0, which
                # means it applies but is expected here.
                continue

            base_penalty = float(penalties[view_value])
            penalty = (
                base_penalty
                * severity_multiplier(row.default_severity)
                * max(0.0, min(1.0, detection.confidence))
            )

            all_labels = [
                d.raw_label for d in detections if d.label == code
            ]
            findings.append(
                IndicatorFinding(
                    code=code,
                    display_name=row.display_name,
                    view=view_value,
                    severity=row.default_severity,
                    penalty=penalty,
                    confidence=detection.confidence,
                    detection_count=len(all_labels),
                    raw_labels=sorted(set(all_labels)),
                    source=detection.source,
                )
            )

    # Most severe first, so a UI that truncates shows the worst.
    findings.sort(key=lambda f: (-f.penalty, f.code, f.view))
    return findings


def summarise_for_storage(findings: Sequence[IndicatorFinding]) -> List[dict]:
    """Compact form stored on hygiene_checks.indicators_found.

    Deliberately smaller than the full finding: this is the row the reviewer
    dashboard filters on (it is GIN-indexed), so it carries what a filter
    needs and nothing else. The full detail lives on the image rows.
    """
    return [
        {
            "code": finding.code,
            "view": finding.view,
            "confidence": round(finding.confidence, 4),
            "penalty": round(finding.penalty, 2),
        }
        for finding in findings
    ]
