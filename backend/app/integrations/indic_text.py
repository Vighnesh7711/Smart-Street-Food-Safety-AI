"""English-to-Indic text handling for the local IndicTrans2 provider.

Pure Python: no torch, no model, no download. That is deliberate -- it keeps
the text logic unit-testable in the default test suite, which must stay fast
and offline.

WHY THIS IS HAND-WRITTEN
------------------------
IndicTrans2's reference pre/post-processing lives in `IndicTransToolkit`,
whose processor is a Cython extension (`processor.pyx`). It publishes no cp314
wheel, no abi3 wheel, and no Windows wheel at all, so installing it here would
mean compiling C through MSVC -- and it drags Sphinx, pandas, lxml and
Morfessor in as runtime dependencies. This module is a port of the parts we
actually need, with `processor.pyx` (MIT) read as the specification.

THE ONE THING THE MODEL REALLY REQUIRES
---------------------------------------
`tokenization_indictrans.py::_src_tokenize` is:

    src_lang, tgt_lang, text = text.split(" ", 2)
    assert src_lang in LANGUAGE_TAGS, f"Invalid source language tag: {src_lang}"

so the string handed to the tokenizer must be exactly
`f"{src_tag} {tgt_tag} {text}"` -- the tags are literal single tokens in the
source vocabulary (verified: `eng_Latn hin_Deva wheat flour` -> [4, 15, 5680,
2912, 2]). The tokenizer enforces the tag set itself, but we validate first so
a bad language surfaces as our own clear error rather than an AssertionError
from inside remote code.

WHAT IS DELIBERATELY ABSENT
---------------------------
Entity masking. The plan originally called for hiding numbers behind
sentinels, on the theory that a distilled model mangles digits. Measured
against the real model, that theory is wrong and the mitigation is a hazard:

    unmasked   "32 percent ... 500 mg"  -> digits preserved (hi and mr)
    __N0__     -> mangled to "% @ N0 @ %"
    ⟦0⟧        -> brackets stripped, leaving bare "0" and "1"
    X0X/X1X    -> survived

The `⟦0⟧` case fails *silently*: the placeholder becomes indistinguishable from
a real number, so restoring it finds nothing and we would ship wrong
quantities while believing they were protected. So instead of transforming
numbers we merely *check* them -- see `digits_preserved`.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# The source language of every string this application translates. The vendor
# UI is localized *out* of English; English is canonical everywhere else.
SOURCE_TAG = "eng_Latn"

# Our public language codes -> IndicTrans2 (FLORES-200) tags. The application
# keeps "hi"/"mr" (`settings.SUPPORTED_LANGUAGES`); the tags are an internal
# detail of the model, and this map is the only place they appear.
APP_TO_TAG: Dict[str, str] = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "mr": "mar_Deva",
}

# Copied verbatim from `tokenization_indictrans.py::LANGUAGE_TAGS`. Kept in
# sync with the model on purpose: validating against our own smaller set would
# let a tag through that the tokenizer then rejects.
LANGUAGE_TAGS = frozenset(
    {
        "asm_Beng", "awa_Deva", "ben_Beng", "bho_Deva", "brx_Deva", "doi_Deva",
        "eng_Latn", "gom_Deva", "gon_Deva", "guj_Gujr", "hin_Deva", "hne_Deva",
        "kan_Knda", "kas_Arab", "kas_Deva", "kha_Latn", "lus_Latn", "mag_Deva",
        "mai_Deva", "mal_Mlym", "mar_Deva", "mni_Beng", "mni_Mtei", "npi_Deva",
        "ory_Orya", "pan_Guru", "san_Deva", "sat_Olck", "snd_Arab", "snd_Deva",
        "tam_Taml", "tel_Telu", "urd_Arab", "unr_Deva",
    }
)

# Sentence terminators. `।` (danda) is the Devanagari full stop, and appears in
# model output; the rest cover English source text.
_TERMINATORS = frozenset("।?!")

# The model's source cap is 256 tokens (`max_source_positions`), and the
# tokenizer is called with `truncation=True`. Truncation would silently drop
# the tail of a long label, so we split before it can happen. ~600 characters
# is comfortably inside 256 tokens for English text.
MAX_SEGMENT_CHARS = 600

# Clause boundaries used when a single sentence is still over budget.
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")

# Abbreviations that end in a full stop without ending a sentence. Food labels
# are full of `e.g.`, `approx.` and `vs.`, and splitting inside one hands the
# model half an abbreviation.
_ABBREVIATIONS = frozenset(
    {"etc", "vs", "approx", "no", "fig", "cf", "al", "min", "max", "incl"}
)

# The token immediately before a full stop: letters and any dots already seen,
# e.g. "high" in "Fat is high." or "e.g" in "Additives e.g."
_TOKEN_BEFORE_STOP = re.compile(r"([A-Za-z.]+)$")

_DIGIT_RUN = re.compile(r"\d+")


def _ends_abbreviation(text: str, index: int) -> bool:
    """True if the '.' at `index` closes an abbreviation, not a sentence.

    A token that already contains a dot is a dotted initialism (`e.g.`,
    `i.e.`, `A.D.`), and a token in `_ABBREVIATIONS` is a known short form.

    Deliberately *not* treating every single letter as an abbreviation:
    "Contains vitamin A. Add salt." is two sentences, and swallowing that
    boundary would merge them into one translation unit.
    """
    match = _TOKEN_BEFORE_STOP.search(text[:index])
    if not match:
        return False
    token = match.group(1)
    return "." in token or token.lower() in _ABBREVIATIONS


def tag_for(language: Optional[str], default: Optional[str] = None) -> Optional[str]:
    """Map an application language code to an IndicTrans2 tag.

    Returns `default` (None unless given) for anything unmapped, so callers
    decide between "fall back to English" and "unsupported language".
    """
    if not language:
        return default
    return APP_TO_TAG.get(language.strip().lower(), default)


def validate_tag(tag: str, *, role: str) -> str:
    """Raise a clear error for a tag the model does not know."""
    if tag not in LANGUAGE_TAGS:
        raise ValueError(
            f"Unsupported IndicTrans2 {role} tag {tag!r}. "
            f"Known tags are the FLORES-200 codes in LANGUAGE_TAGS."
        )
    return tag


def split_sentences(text: str) -> List[str]:
    """Split into sentences, keeping each terminator attached.

    A terminator only ends a sentence when whitespace (or end-of-string)
    follows, which is what keeps `32.5` and `e.g.` in one piece -- splitting
    mid-number would hand the model a broken quantity.
    """
    sentences: List[str] = []
    current: List[str] = []

    for index, char in enumerate(text):
        current.append(char)
        if char not in _TERMINATORS and char != ".":
            continue

        following = text[index + 1] if index + 1 < len(text) else ""
        if following and not following.isspace():
            continue
        if char == ".":
            if (
                index > 0
                and text[index - 1].isdigit()
                and following.isdigit()
            ):
                continue
            if _ends_abbreviation(text, index):
                continue

        sentence = "".join(current).strip()
        if sentence:
            sentences.append(sentence)
        current = []

    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)
    return sentences


def _split_over_budget(segment: str, budget: int) -> List[str]:
    """Break one long segment at clause boundaries, then at whitespace.

    Only reached for a single sentence longer than `budget`. Preferring commas
    keeps the pieces grammatical, which matters because each is translated on
    its own.
    """
    if len(segment) <= budget:
        return [segment]

    pieces: List[str] = []
    chunk = ""
    for clause in _CLAUSE_SPLIT.split(segment):
        candidate = f"{chunk} {clause}".strip() if chunk else clause
        if len(candidate) <= budget:
            chunk = candidate
            continue
        if chunk:
            pieces.append(chunk)
            chunk = ""
        # A single clause can still be over budget; fall back to words.
        if len(clause) <= budget:
            chunk = clause
            continue
        for word in clause.split():
            candidate = f"{chunk} {word}".strip() if chunk else word
            if len(candidate) <= budget:
                chunk = candidate
            else:
                if chunk:
                    pieces.append(chunk)
                chunk = word
    if chunk:
        pieces.append(chunk)
    return pieces


def preprocess(
    text: str,
    target_tag: str,
    source_tag: str = SOURCE_TAG,
    *,
    max_chars: int = MAX_SEGMENT_CHARS,
) -> List[str]:
    """Turn one English string into model-ready, tag-prefixed segments.

    Returns one entry per sentence, in order. The caller tokenizes the list as
    a batch, so a two-sentence explanation is still a single `generate()` call.
    """
    validate_tag(source_tag, role="source")
    validate_tag(target_tag, role="target")

    if not text or not text.strip():
        return []

    segments: List[str] = []
    for sentence in split_sentences(text):
        segments.extend(_split_over_budget(sentence, max_chars))

    return [f"{source_tag} {target_tag} {segment}" for segment in segments]


def postprocess(segments: List[str]) -> str:
    """Rejoin translated segments into one string.

    The tokenizer's `convert_tokens_to_string` already turns `▁` back into
    spaces and strips, but a segment can still arrive empty (the model emitted
    only special tokens), so empties are dropped rather than leaving a doubled
    space where a sentence used to be.
    """
    cleaned = [" ".join(segment.split()) for segment in segments if segment]
    return " ".join(part for part in cleaned if part).strip()


def digits_preserved(source: str, translated: str) -> bool:
    """True if `translated` carries exactly the numbers `source` did.

    The measurement above says the model preserves digits on its own, so this
    is a detector, not a guard: it never rewrites text, so it cannot corrupt
    anything. When it goes false we know a label's quantities are suspect --
    see the module docstring for why masking is not the answer.

    Compares whole digit runs, so `32` becoming `23` is caught, not just a
    number disappearing.
    """
    return Counter(_DIGIT_RUN.findall(source)) == Counter(
        _DIGIT_RUN.findall(translated)
    )
