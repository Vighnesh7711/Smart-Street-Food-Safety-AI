"""Perceptual hashing, to catch the same photo submitted for two views.

Coverage validation relies on the vendor tagging each photo with the view it
shows (see coverage.py). Tagging is cheap and unverifiable, so the obvious
abuse is uploading one photo four times under four different tags.

This does not make the check tamper-proof and does not try to. It catches
the laziest version of that abuse for essentially free, and the reviewer can
always see all four photos side by side.

`cv2.img_hash` would do this, but it lives in opencv-contrib and is not
available in the headless build used here. A difference hash is about fifteen
lines, so it is implemented directly rather than pulling in another package.
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

#: 8x8 difference hash -> 64 bits -> 16 hex characters.
_HASH_SIZE = 8
_HEX_WIDTH = _HASH_SIZE * _HASH_SIZE // 4


def dhash(image_bgr: np.ndarray, hash_size: int = _HASH_SIZE) -> str:
    """Compute a difference hash, returned as a hex string.

    dHash compares each pixel with its right-hand neighbour, so it encodes
    the *gradient* structure of the image rather than absolute brightness.
    That makes it robust to the exposure and white-balance differences you
    get between two photos of the same scene, while still distinguishing two
    genuinely different scenes.

    Deliberately not a cryptographic hash: the point is to match photos that
    are the same scene, not to detect a byte-identical file.
    """
    if image_bgr is None or image_bgr.size == 0:
        return ""

    # One extra column so there are hash_size differences per row.
    resized = cv2.resize(
        image_bgr, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA
    )
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.int16)

    # Compare each pixel with its right-hand neighbour, row-major.
    differences = gray[:, 1:] > gray[:, :-1]
    bits = differences.flatten()

    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:0{_HEX_WIDTH}x}"


def hamming_distance(left: str, right: str) -> int:
    """Number of differing bits between two hex-encoded hashes.

    64 returns on any malformed input, which reads as "definitely not a
    duplicate" -- the safe direction, since the cost of a false duplicate
    rejection is a vendor being unable to submit a legitimate photo.
    """
    if not left or not right:
        return 64
    try:
        return bin(int(left, 16) ^ int(right, 16)).count("1")
    except ValueError:
        return 64


def is_duplicate(left: str, right: str, threshold: int) -> bool:
    return hamming_distance(left, right) <= threshold


def find_duplicate(
    candidate_hash: str,
    existing: list[tuple[int, str]],
    threshold: int,
) -> Optional[tuple[int, int]]:
    """Return (image_id, distance) of the closest match within threshold.

    `existing` is a list of (image_id, phash) from the same check. Comparison
    is scoped to one check on purpose: the same stall photographed on two
    different days is legitimate and must not be flagged, and a vendor
    photographing the same wall twice a week apart is not the abuse this is
    looking for.
    """
    if not candidate_hash:
        return None

    best: Optional[tuple[int, int]] = None
    for image_id, existing_hash in existing:
        distance = hamming_distance(candidate_hash, existing_hash)
        if distance <= threshold and (best is None or distance < best[1]):
            best = (image_id, distance)
    return best
