"""Locate the ingredient list inside raw OCR text.

A label is mostly things we do not want: nutrition tables, storage advice,
manufacturer addresses, barcodes. Sending all of it to the matcher would
produce nonsense matches ("Energy", "Protein", "Store in a cool dry place"),
so this stage slices out just the ingredient declaration first.

Multilingual anchors are included because Indian packaged food commonly
carries the declaration in Hindi or Marathi as well as English, and a
Devanagari-only label is exactly the case a street vendor is most likely to
photograph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# Headings that introduce the ingredient declaration.
_ANCHOR_PATTERNS = [
    r"ingredients?\s*(?:list)?\s*[:\-–]",
    r"ingredients?\s*(?:list)?\b",
    r"contains\s*[:\-–]",
    # Hindi / Marathi
    r"सामग्री\s*[:\-–]?",
    r"घटक\s*[:\-–]?",
    r"अवयव\s*[:\-–]?",
]

# Headings that end the ingredient declaration and start something else.
_TERMINATOR_PATTERNS = [
    r"nutrition(?:al)?\s*(?:information|facts|value)",
    r"typical\s+values?",
    r"allergen",
    r"storage",
    r"store\s+in",
    r"best\s+before",
    r"use\s+by",
    r"expiry",
    r"batch\s+no",
    r"manufactured\s+(?:by|at)",
    r"marketed\s+by",
    r"packed\s+by",
    r"net\s+(?:weight|qty|quantity)",
    r"net\s+wt",
    r"mrp",
    r"customer\s+care",
    r"directions?\s+for\s+use",
    r"usage",
    r"serving\s+suggestion",
    r"fssai\s+lic",
    # Hindi / Marathi
    r"पोषण",
    r"पोषक",
    r"संग्रहण",
    r"संचयन",
    r"निर्माता",
    r"शुद्ध\s+वजन",
    r"एफएसएसएआई",
]

_ANCHOR_RE = re.compile("|".join(_ANCHOR_PATTERNS), re.IGNORECASE | re.UNICODE)
_TERMINATOR_RE = re.compile("|".join(_TERMINATOR_PATTERNS), re.IGNORECASE | re.UNICODE)

# A section shorter than this is almost certainly a mis-slice rather than a
# real ingredient list.
_MIN_SECTION_CHARS = 12


@dataclass
class ExtractionResult:
    section: str
    """The sliced ingredient declaration, or the whole text as a fallback."""

    anchor_found: bool
    anchor_text: Optional[str] = None
    truncated_at: Optional[str] = None
    """The terminator that ended the section, for debugging odd layouts."""

    @property
    def is_usable(self) -> bool:
        return len(self.section.strip()) >= _MIN_SECTION_CHARS


def _clean(text: str) -> str:
    """Collapse OCR whitespace while preserving line structure."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_ingredient_section(raw_text: str) -> ExtractionResult:
    """Slice the ingredient declaration out of raw OCR text.

    Falls back to the whole text when no anchor is found -- a label whose
    heading OCR mangled still has usable ingredient text, and discarding it
    would be worse than matching against a noisy section. `anchor_found`
    records which happened, and the status engine treats an anchorless parse
    as weaker evidence.
    """
    if not raw_text or not raw_text.strip():
        return ExtractionResult(section="", anchor_found=False)

    text = _clean(raw_text)
    anchor_match = _ANCHOR_RE.search(text)

    if anchor_match is None:
        return ExtractionResult(section=text, anchor_found=False)

    start = anchor_match.end()
    remainder = text[start:]
    terminator = _TERMINATOR_RE.search(remainder)

    if terminator is not None:
        section = remainder[: terminator.start()]
        truncated_at = terminator.group(0)
    else:
        section = remainder
        truncated_at = None

    section = section.strip(" \n:;-–")

    # Guard against a false anchor: "contains" appears in marketing copy
    # ("contains no added sugar") far more often than as a heading. If the
    # slice is implausibly short, fall back to the full text rather than
    # reporting a near-empty ingredient list.
    if len(section) < _MIN_SECTION_CHARS:
        return ExtractionResult(section=text, anchor_found=False)

    return ExtractionResult(
        section=section,
        anchor_found=True,
        anchor_text=anchor_match.group(0).strip(),
        truncated_at=truncated_at,
    )


def find_all_anchors(raw_text: str) -> List[str]:
    """Every anchor-like heading in the text. Exposed for tests/debugging."""
    return [m.group(0).strip() for m in _ANCHOR_RE.finditer(raw_text or "")]
