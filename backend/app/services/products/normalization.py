"""Text normalization for label OCR output and knowledge-base aliases.

Everything the matcher compares -- label tokens and knowledge-base aliases --
goes through `normalize_alias`. Keeping one function for both sides is what
makes matching an equality check rather than a pile of special cases.

Two details that are easy to get wrong:

1. **Devanagari combining marks.** A naive `re.sub(r"[^\\w\\s]", " ", s)`
   strips matras, because Unicode combining marks (category `Mn`) are not
   "alphanumeric" and so are not matched by `\\w`. That silently mangles
   Hindi and Marathi: "सामग्री" becomes "सामगर". Characters are therefore
   filtered by Unicode category (letters, marks, numbers) rather than by a
   regex character class.

2. **INS/E numbers.** Indian labels write preservatives as "INS 211",
   "INS-211", "E211", or "(211)". All are canonicalised to "e211" so one
   synonym row covers every printed form.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

# Matches an INS or E number in any of its printed forms.
#   INS 211 / INS-211 / INS211 / E 211 / E211
_E_NUMBER_RE = re.compile(
    r"^(?:ins|e)\s*[-–]?\s*(\d{3,4}[a-z]?)$",
    re.IGNORECASE,
)

# A percentage, optionally parenthesised: "2.5%", "(2.5 %)".
_PERCENT_RE = re.compile(r"\(?\s*(\d+(?:[.,]\d+)?)\s*%\s*\)?")

# Separators between ingredients on a label. "and"/"&" are included because
# labels often write "Salt and permitted preservatives".
_SPLIT_RE = re.compile(
    r"[,;•·|/]|\band\b|&|\n|\r",
    re.IGNORECASE,
)

# Boilerplate that appears inside ingredient lists but carries no meaning.
# Stripped so it cannot become a phantom token.
#
# The section anchors ("ingredients", "सामग्री", "घटक") are included because
# OCR frequently returns the heading glued to the first real ingredient --
# "Ingredients: Refined Wheat Flour" -- and ingredient_extraction cannot be
# relied on to have split them cleanly for every label layout.
_NOISE_PHRASES = (
    "ingredients",
    "ingredient",
    "सामग्री",
    "घटक",
    "contains permitted",
    "permitted natural colour",
    "permitted synthetic colour",
    "added flavour",
    "added flavours",
    "added flavor",
    "added flavors",
    "contains",
    "added",
    "permitted",
    "natural",
    "artificial",
    "synthetic",
)

# Leading/trailing filler left behind after noise removal.
_EDGE_FILLER_RE = re.compile(r"^[\s\-–.:]+|[\s\-–.:]+$")

# Character class used for word boundaries around noise phrases.
#
# NOT `\b`. Python's `\b` is defined in terms of `\w`, and `\w` does not
# match combining marks -- 'ी' in "सामग्री" has Unicode category Mn and is
# not `str.isalnum()`. So `\bसामग्री\b` never matches: there is no boundary
# between the trailing matra and the following space, because both are
# non-word characters. The Devanagari block is therefore added explicitly.
# (Same root cause as the `_keep_char` note above.)
_BOUNDARY_CHARS = r"\wऀ-ॿ"


def _keep_char(char: str) -> bool:
    """Keep letters, combining marks, numbers, and whitespace.

    Category-based rather than regex-based so Devanagari vowel signs survive.
    """
    if char.isspace():
        return True
    category = unicodedata.category(char)
    return category[0] in ("L", "M", "N")


def canonicalize_e_number(token: str) -> Optional[str]:
    """Return "e211" for "INS 211"/"E211", or None if not an E/INS number."""
    cleaned = token.strip().strip("()[]").strip()
    match = _E_NUMBER_RE.match(cleaned)
    if not match:
        return None
    return f"e{match.group(1).lower()}"


def normalize_alias(text: str) -> str:
    """Canonical comparison form for both aliases and label tokens.

    Casefolded, Unicode-normalized, stripped of punctuation, whitespace
    collapsed. E/INS numbers collapse to the single "eNNN" form.
    """
    if not text:
        return ""

    e_number = canonicalize_e_number(text)
    if e_number:
        return e_number

    # NFC first so visually identical Devanagari sequences compare equal.
    decomposed = unicodedata.normalize("NFC", text)
    kept = "".join(char if _keep_char(char) else " " for char in decomposed)
    # casefold() over lower() for correct handling of non-ASCII cases.
    collapsed = " ".join(kept.casefold().split())

    # The E-number check runs again because punctuation removal can expose a
    # form the first pass missed, e.g. "(INS-211)".
    return canonicalize_e_number(collapsed) or collapsed


def strip_noise(text: str) -> str:
    """Remove label boilerplate that would otherwise become phantom tokens."""
    result = text
    for phrase in _NOISE_PHRASES:
        # Lookarounds rather than \b -- see _BOUNDARY_CHARS. Without this,
        # "added" would also eat "additive" and Devanagari anchors would
        # never match at all.
        pattern = (
            rf"(?<![{_BOUNDARY_CHARS}])"
            rf"{re.escape(phrase)}"
            rf"(?![{_BOUNDARY_CHARS}])"
        )
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    return _EDGE_FILLER_RE.sub("", " ".join(result.split()))


@dataclass
class ParsedToken:
    """One candidate ingredient parsed out of a label's ingredient section."""

    raw: str
    """The original substring, kept for match evidence."""

    normalized: str
    """Comparison form; empty when the token reduced to nothing."""

    percent: Optional[float] = None
    """Percentage declared on the label, if any. Threshold rules use this."""

    position: int = 0
    """Character offset in the ingredient section, for UI highlighting."""

    @property
    def is_e_number(self) -> bool:
        return bool(re.fullmatch(r"e\d{3,4}[a-z]?", self.normalized))


def parse_ingredient_section(section: str) -> List[ParsedToken]:
    """Split an ingredient section into normalized tokens.

    Percentages are extracted *before* normalization and removed from the
    text, so "Sugar (15%)" yields token "sugar" with percent 15.0 rather
    than the unmatchable "sugar 15".
    """
    tokens: List[ParsedToken] = []
    if not section:
        return tokens

    pieces = _SPLIT_RE.split(section)
    cursor = 0
    for piece in pieces:
        raw_piece = piece.strip()
        if not raw_piece:
            cursor += len(piece) + 1
            continue

        percent: Optional[float] = None
        percent_match = _PERCENT_RE.search(raw_piece)
        if percent_match:
            try:
                percent = float(percent_match.group(1).replace(",", "."))
            except ValueError:
                percent = None
            raw_piece = _PERCENT_RE.sub(" ", raw_piece).strip()

        # Strip a trailing quantity that is not a percentage, e.g. "Salt 2g".
        # It carries no matching value and would otherwise create "salt 2g".
        raw_piece = re.sub(
            r"\b\d+(?:[.,]\d+)?\s*(?:g|gm|gms|mg|kg|ml|%)\b",
            " ",
            raw_piece,
            flags=re.IGNORECASE,
        )

        cleaned = strip_noise(raw_piece)
        normalized = normalize_alias(cleaned)

        # Drop leftovers that are pure punctuation or a bare number.
        if not normalized or normalized.isdigit():
            cursor += len(piece) + 1
            continue
        # Single letters are OCR debris, not ingredients.
        if len(normalized) < 2:
            cursor += len(piece) + 1
            continue

        tokens.append(
            ParsedToken(
                raw=raw_piece,
                normalized=normalized,
                percent=percent,
                position=cursor,
            )
        )
        cursor += len(piece) + 1

    return tokens
