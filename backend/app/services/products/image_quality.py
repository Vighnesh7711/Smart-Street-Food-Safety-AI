"""Image-quality gate for label photos.

Runs before OCR on purpose. A blurred or glared photo produces garbage OCR,
and OCR is a paid network call -- rejecting the image first saves both the
money and the vendor's time, and lets us say something specific ("hold
steady") instead of "could not read label".

Everything here is classical OpenCV. There is no model to download and no
network call, so it is also the cheapest stage to run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np

from app.core.config import settings


@dataclass
class ImageQualityReport:
    ok: bool
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    guidance: Optional[str] = None
    """One actionable sentence for the vendor, e.g. "The photo is blurry --
    hold the phone steady and try again." None when ok is True."""

    width: int = 0
    height: int = 0

    @property
    def sharpness_score(self) -> float:
        """Blur metric squashed into [0, 1].

        Used as the OCR-confidence fallback when the provider does not report
        per-word confidence -- see integrations/ocr_client.py. Calibrated so
        that the configured minimum (SCAN_MIN_BLUR_VARIANCE) maps to roughly
        0.5 rather than 0, because a photo at the rejection threshold is
        marginal, not worthless.
        """
        variance = self.metrics.get("blur_variance", 0.0)
        threshold = max(settings.SCAN_MIN_BLUR_VARIANCE, 1.0)
        # variance/threshold is 1.0 at the threshold; 1 - e^-x maps
        # [0, inf) -> [0, 1) with 0.63 at the threshold.
        return float(1.0 - np.exp(-variance / threshold))

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "issues": self.issues,
            "metrics": self.metrics,
            "guidance": self.guidance,
            "width": self.width,
            "height": self.height,
        }


def _decode(image_bytes: bytes) -> Optional[np.ndarray]:
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    if buffer.size == 0:
        return None
    # IMREAD_COLOR drops any alpha channel, which OCR does not need and which
    # would otherwise break the single-channel grayscale math below.
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def assess(image_bytes: bytes) -> ImageQualityReport:
    """Evaluate whether a label photo is worth sending to OCR."""
    image = _decode(image_bytes)
    if image is None:
        return ImageQualityReport(
            ok=False,
            issues=["unreadable_image"],
            guidance="That file could not be read as an image. Please retake the photo.",
        )

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # --- Blur: variance of the Laplacian. Low variance = few sharp edges. ---
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # --- Exposure ---
    mean_brightness = float(gray.mean())
    # Fraction of pixels crushed to black or blown to white. A photo can have
    # a reasonable mean and still be useless if half of it is blown out.
    clipped_high = float((gray >= 250).mean())
    clipped_low = float((gray <= 5).mean())

    # --- Glare: specular highlights on laminated packaging. These are
    # saturated *and* locally flat, which distinguishes them from a white
    # background (flat but not usually 250+).
    glare_ratio = float((gray >= 245).mean())

    metrics = {
        "blur_variance": round(blur_variance, 2),
        "mean_brightness": round(mean_brightness, 2),
        "clipped_high_ratio": round(clipped_high, 4),
        "clipped_low_ratio": round(clipped_low, 4),
        "glare_ratio": round(glare_ratio, 4),
        "width": float(width),
        "height": float(height),
        "aspect_ratio": round(width / height, 3) if height else 0.0,
    }

    issues: List[str] = []

    if min(width, height) < settings.SCAN_MIN_IMAGE_EDGE:
        issues.append("too_small")

    if blur_variance < settings.SCAN_MIN_BLUR_VARIANCE:
        issues.append("blurry")

    if mean_brightness < settings.SCAN_MIN_BRIGHTNESS:
        issues.append("too_dark")
    elif mean_brightness > settings.SCAN_MAX_BRIGHTNESS:
        issues.append("too_bright")

    if clipped_high > 0.25:
        issues.append("overexposed")
    if clipped_low > 0.25:
        issues.append("underexposed")

    if glare_ratio > settings.SCAN_MAX_GLARE_RATIO:
        issues.append("glare")

    return ImageQualityReport(
        ok=not issues,
        issues=issues,
        metrics=metrics,
        guidance=_guidance_for(issues),
        width=width,
        height=height,
    )


_GUIDANCE = {
    "blurry": "The photo is blurry. Hold the phone steady and tap to focus, then retake.",
    "too_small": "The label is too small in the frame. Move closer and fill the guide with the ingredient list.",
    "too_dark": "It is too dark. Move to better light or turn on your phone torch.",
    "underexposed": "Parts of the label are too dark to read. Improve the lighting and retake.",
    "too_bright": "The photo is too bright or washed out. Move away from direct light.",
    "overexposed": "Bright light is washing out the label. Tilt the packet away from the light source.",
    "glare": "There is glare on the packet. Tilt it slightly so the light does not reflect into the camera.",
    "unreadable_image": "That file could not be read as an image. Please retake the photo.",
}


def _guidance_for(issues: List[str]) -> Optional[str]:
    """Pick the most actionable single instruction.

    Vendors get one sentence, not a list. Ordering matters: a blurry photo is
    fixed by holding still, whereas glare needs the packet tilted, and doing
    both at once is harder than doing one.
    """
    for issue in (
        "unreadable_image",
        "blurry",
        "glare",
        "too_dark",
        "underexposed",
        "too_bright",
        "overexposed",
        "too_small",
    ):
        if issue in issues:
            return _GUIDANCE[issue]
    return None


def prepare_for_ocr(image_bytes: bytes) -> bytes:
    """Downscale oversized uploads before sending them to OCR.

    Phone cameras produce 12MP+ images. Vision's accuracy does not improve
    meaningfully past ~1600px on the long edge for label text, but payload
    size and latency both scale with pixels. Returns the original bytes if
    it is already small enough or cannot be decoded.
    """
    image = _decode(image_bytes)
    if image is None:
        return image_bytes

    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= settings.SCAN_MAX_IMAGE_EDGE:
        return image_bytes

    scale = settings.SCAN_MAX_IMAGE_EDGE / longest
    resized = cv2.resize(
        image,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    ok, buffer = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return image_bytes
    return buffer.tobytes()
