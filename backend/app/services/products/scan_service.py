"""The product-scan pipeline.

    image bytes
      -> image-quality gate        (OpenCV, local)
      -> OCR                       (Cloud Vision)
      -> ingredient-section slice
      -> normalize + parse
      -> knowledge-base match
      -> rule evaluation
      -> confidence + status
      -> English explanation
      -> translation to the vendor's language

Runs synchronously inside the request. The mobile UI shows a loading state
for the duration. If OCR latency becomes a problem, the natural upgrade is
to move stages 2 onward into app/workers/ and return a job id -- see
workers/README.md. Everything below is already expressed as a pure function
of its inputs, so that move does not require rewriting the logic.

A scan is always persisted, including failures the vendor can act on
(blurry photo, unreadable label), because the history is what the reviewer
dashboard reads and a vendor's retry pattern is itself a signal.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations import ocr_client, translate_client
from app.models.enums import ScanStatus
from app.models.product import Product
from app.models.product_ingredient import ProductIngredient
from app.models.stall import Stall
from app.models.user import User
from app.services.products import (
    explanation as explanation_service,
    image_quality,
    ingredient_extraction,
    matching,
    normalization,
    status_engine,
)
from app.services.products.status_engine import Confidences, RuleOutcome

logger = logging.getLogger(__name__)


class ScanError(RuntimeError):
    """The scan could not be completed at all.

    Distinct from a scan that returns a negative verdict: this means no
    assessment was possible (OCR unavailable, empty upload). Carries a
    user-facing message and whether retrying might help.
    """

    def __init__(self, message: str, user_message: str, retryable: bool = False):
        super().__init__(message)
        self.user_message = user_message
        self.retryable = retryable


@dataclass
class ScanOutcome:
    product: Product
    matches: List[matching.IngredientMatch] = field(default_factory=list)
    outcomes: List[RuleOutcome] = field(default_factory=list)
    confidences: Optional[Confidences] = None
    recommendations: List[str] = field(default_factory=list)
    quality: Optional[image_quality.ImageQualityReport] = None


def _validate_upload(image_bytes: bytes) -> None:
    if not image_bytes:
        raise ScanError("Empty upload", "No image was received. Please retake.")

    limit = int(settings.SCAN_MAX_UPLOAD_MB * 1024 * 1024)
    if len(image_bytes) > limit:
        raise ScanError(
            f"Upload {len(image_bytes)} bytes exceeds {limit}",
            f"That image is larger than {settings.SCAN_MAX_UPLOAD_MB:g} MB. "
            "Please retake at a smaller size.",
        )


def save_upload(image_bytes: bytes) -> str:
    """Persist the uploaded label image and return its root-relative path.

    Stored under a random name rather than a vendor-supplied one: filenames
    from a phone can collide, and a client-controlled path is a traversal
    risk. The returned path is what gets served from the static mount.
    """
    directory = settings.scan_upload_path
    directory.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.jpg"
    (directory / filename).write_bytes(image_bytes)

    # Root-relative so the API can be served from any host; the client joins
    # it to the API origin.
    return f"/uploads/scans/{filename}"


def _persist(
    db: Session,
    *,
    stall: Stall,
    user: User,
    image_path: str,
    status: ScanStatus,
    explanation_text: str,
    translated_text: str,
    language_code: str,
    translation_failed: bool,
    confidences: Optional[Confidences],
    quality: image_quality.ImageQualityReport,
    ocr_text: str,
    ocr_confidence: Optional[float],
    ingredient_text: Optional[str],
    retake_required: bool,
    matches: List[matching.IngredientMatch],
) -> Product:
    product = Product(
        stall_id=stall.id,
        name=None,
        ingredients_text=ingredient_text,
        status=status.value,
        explanation=explanation_text,
        explanation_translated=translated_text,
        language_code=language_code,
        translation_failed=translation_failed,
        scan_image_path=image_path,
        ocr_raw_text=ocr_text or None,
        ocr_confidence=ocr_confidence,
        match_confidence=confidences.match if confidences else None,
        rule_strength=confidences.rule if confidences else None,
        confidence_score=confidences.overall if confidences else None,
        image_quality=quality.to_dict(),
        retake_required=retake_required,
        scanned_by_user_id=user.id,
    )
    db.add(product)
    db.flush()

    for match in matches:
        db.add(
            ProductIngredient(
                product_id=product.id,
                ingredient_id=match.ingredient.id,
                matched_text=(match.matched_text or "")[:300] or None,
                matched_alias=(match.matched_alias or "")[:200] or None,
                match_confidence=match.confidence,
                match_method=match.method.value,
                position_in_text=match.position,
                parsed_percent=match.parsed_percent,
            )
        )
    db.flush()
    return product


def scan_label(
    db: Session,
    *,
    stall: Stall,
    user: User,
    image_bytes: bytes,
    target_language: Optional[str] = None,
) -> ScanOutcome:
    """Run the full pipeline for one label photo.

    `target_language` defaults to the vendor's preferred_language, falling
    back to English (which is a passthrough, never an API call).
    """
    _validate_upload(image_bytes)

    language = (target_language or user_vendor_language(db, user) or "en").lower()

    # --- 1. Image quality gate. Cheapest stage, and it protects the paid
    #        OCR call from obviously unusable input. ---
    quality = image_quality.assess(image_bytes)
    image_path = save_upload(image_bytes)

    if not quality.ok:
        # Short-circuit: no OCR, no matching. Persisted so the vendor sees it
        # in history and the reviewer can spot a struggling stall.
        message = quality.guidance or "The photo was not clear enough to read."
        translated, failed = _translate(message, language)
        product = _persist(
            db,
            stall=stall,
            user=user,
            image_path=image_path,
            status=ScanStatus.NEEDS_REVIEW,
            explanation_text=message,
            translated_text=translated,
            language_code=language,
            translation_failed=failed,
            confidences=None,
            quality=quality,
            ocr_text="",
            ocr_confidence=None,
            ingredient_text=None,
            retake_required=True,
            matches=[],
        )
        db.commit()
        db.refresh(product)
        return ScanOutcome(product=product, quality=quality)

    # --- 2. OCR ---
    try:
        ocr_result = ocr_client.run_ocr(image_quality.prepare_for_ocr(image_bytes))
    except ocr_client.OcrError as exc:
        # No scan exists yet, so there is nothing to persist -- surface it.
        logger.error("OCR failed for stall %s: %s", stall.id, exc)
        raise ScanError(str(exc), exc.user_message, retryable=exc.retryable) from exc

    # --- 3. Slice the ingredient declaration out of the label text ---
    extraction = ingredient_extraction.extract_ingredient_section(ocr_result.text)

    # --- 4. Normalize into candidate tokens ---
    tokens = normalization.parse_ingredient_section(extraction.section)

    # --- 5. Match against the knowledge base ---
    kb = matching.load_knowledge_base(db)
    matches = matching.match_tokens(tokens, kb) if kb else []

    # --- 6. Evaluate rules ---
    outcomes = status_engine.evaluate_rules(matches, stall.food_category)

    # --- 7. Confidence + status ---
    ocr_confidence = status_engine.resolve_ocr_confidence(
        reported=ocr_result.confidence,
        sharpness_score=quality.sharpness_score,
        anchor_found=extraction.anchor_found,
        token_count=len(tokens),
    )
    confidences = status_engine.compute_confidences(
        ocr_confidence=ocr_confidence,
        matches=matches,
        token_count=len(tokens),
        outcomes=outcomes,
    )
    decision = status_engine.decide_status(
        image_ok=True,
        image_guidance=None,
        anchor_found=extraction.anchor_found,
        token_count=len(tokens),
        matches=matches,
        outcomes=outcomes,
        confidences=confidences,
    )

    # --- 8. English explanation (canonical) ---
    english = explanation_service.build_explanation(decision, outcomes, matches)
    recommendations = explanation_service.collect_recommendations(outcomes, matches)

    # --- 9. Translate, with graceful fallback to English ---
    translated, translation_failed = _translate(english, language)
    if recommendations:
        # Recommendations are translated in the same batch, so a scan makes
        # one translate call rather than one per string.
        translated_recommendations, rec_failed = _translate_many(
            recommendations, language
        )
        translation_failed = translation_failed or rec_failed
    else:
        translated_recommendations = []

    product = _persist(
        db,
        stall=stall,
        user=user,
        image_path=image_path,
        status=decision.status,
        explanation_text=english,
        translated_text=translated,
        language_code=language,
        translation_failed=translation_failed,
        confidences=confidences,
        quality=quality,
        ocr_text=ocr_result.text,
        ocr_confidence=(
            ocr_result.confidence if ocr_result.confidence is not None else ocr_confidence
        ),
        ingredient_text=extraction.section or None,
        retake_required=decision.retake_required,
        matches=matches,
    )
    db.commit()
    db.refresh(product)

    return ScanOutcome(
        product=product,
        matches=matches,
        outcomes=outcomes,
        confidences=confidences,
        recommendations=translated_recommendations,
        quality=quality,
    )


def user_vendor_language(db: Session, user: User) -> Optional[str]:
    """The vendor's preferred language, or None if there is no vendor profile."""
    from app.crud import vendor as crud_vendor

    vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
    return vendor.preferred_language if vendor else None


def _translate(text: str, language: str) -> tuple[str, bool]:
    """Translate, returning (text, failed). Never raises."""
    result = translate_client.translate_text(text, language)
    return result.text, result.warning is not None


def _translate_many(texts: List[str], language: str) -> tuple[List[str], bool]:
    results = translate_client.translate_many(texts, language)
    failed = any(r.warning is not None for r in results)
    return [r.text for r in results], failed
