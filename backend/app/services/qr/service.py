"""QR code lifecycle and rendering.

This module has two halves:

  * Lifecycle functions that touch the database (issue, resolve, revoke).
  * `render_png`, which is pure -- it turns a string into PNG bytes and knows
    nothing about stalls. That split is deliberate: the rendering path is
    what a vendor's printed sticker depends on, so it is unit-testable
    without a database.
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime, timezone
from typing import Optional

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from sqlalchemy.orm import Session

from app.models.qr_code import QrCode
from app.models.stall import Stall

# Crockford-style alphabet: no I, L, O, or U. These codes get read aloud,
# typed from a damaged sticker, and pasted into a URL, so the characters most
# often confused with one another (1/I/L, 0/O) are excluded -- as is U, which
# keeps random codes from spelling unfortunate words.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_LENGTH = 10

# 32**10 ~= 1.1e15 combinations. The unique constraint is the real guarantee;
# this bound just stops an infinite loop under pathological collisions.
_MAX_ATTEMPTS = 12

# --- Rendering ---------------------------------------------------------
#: Error correction M recovers roughly 15% of the code's *data* modules.
#: Worth it for a sticker that lives outdoors and gets scuffed.
#:
#: Note the limit, because it is easy to assume more protection than exists:
#: error correction does NOT protect the three finder patterns in the
#: corners. Damage covering one of those makes the code undetectable at any
#: level, which is why the vendor screen draws it on a plain white card with
#: nothing overlapping it. See test_qr_rendering.py.
_ERROR_CORRECTION = ERROR_CORRECT_M

#: Modules for a short URL are ~29, so box_size=20 gives a ~740px image --
#: comfortably printable at 300dpi and large enough for a phone camera to
#: lock onto from a normal distance.
_DEFAULT_BOX_SIZE = 20
_MIN_BOX_SIZE = 4
_MAX_BOX_SIZE = 60

#: Quiet zone. The spec requires 4 modules; without it many scanners fail.
_BORDER_MODULES = 4


def generate_code() -> str:
    """Return a random, human-transcribable stall code."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


def normalize_code(raw: str) -> str:
    """Canonical form of a user- or scan-supplied code.

    Uppercased and stripped of surrounding whitespace so that a code typed in
    lowercase, or pasted with a trailing space, still resolves. The alphabet
    is uppercase, so uppercasing is lossless.
    """
    return (raw or "").strip().upper()


def generate_unique_code(db: Session) -> str:
    """Return a code not already present in `qr_codes`.

    Checks the whole table, not just active rows: a revoked code must never
    be reissued, or a sticker that was deliberately retired would start
    resolving again to whatever stall received the recycled value.
    """
    for _ in range(_MAX_ATTEMPTS):
        candidate = generate_code()
        if get_by_code(db, candidate) is None:
            return candidate
    raise RuntimeError(
        f"Could not generate a unique QR code after {_MAX_ATTEMPTS} attempts "
        "-- the qr_codes table may be corrupt."
    )


def get_by_code(db: Session, code: str) -> Optional[QrCode]:
    """Look up any code, active or revoked."""
    normalized = normalize_code(code)
    if not normalized:
        return None
    return db.query(QrCode).filter(QrCode.code == normalized).first()


def resolve_active(db: Session, code: str) -> Optional[QrCode]:
    """Look up an ACTIVE code. Returns None for unknown and revoked alike.

    Callers surface both as the same 404, so the response cannot be used to
    distinguish "never existed" from "was revoked".
    """
    qr_code = get_by_code(db, code)
    if qr_code is None or not qr_code.is_active:
        return None
    return qr_code


def issue_for_stall(db: Session, stall: Stall) -> QrCode:
    """Issue a new active code for a stall.

    Does NOT revoke an existing one -- the caller must do that first, so that
    a failure partway through cannot leave a stall with zero active codes and
    a sticker that no longer resolves. The partial unique index will reject a
    second active code, which is the enforced version of the same rule.
    """
    qr_code = QrCode(
        stall_id=stall.id,
        code=generate_unique_code(db),
        is_active=True,
    )
    db.add(qr_code)
    db.flush()
    return qr_code


def revoke(db: Session, qr_code: QrCode) -> QrCode:
    qr_code.is_active = False
    qr_code.revoked_at = datetime.now(timezone.utc)
    db.flush()
    return qr_code


def replace_for_stall(db: Session, stall: Stall) -> QrCode:
    """Revoke any active code and issue a replacement.

    Revoke-then-issue in one transaction. Not wired to an endpoint yet (the
    schema supports it; the UI does not), but implemented and tested so the
    ordering rule lives in one place rather than being rediscovered.
    """
    for existing in list(stall.qr_codes):
        if existing.is_active:
            revoke(db, existing)
    return issue_for_stall(db, stall)


# --- Rendering ---------------------------------------------------------


def build_public_url(code: str, base_url: str) -> str:
    """The payload encoded into the QR image.

    A full URL rather than a bare code, so a consumer can point their normal
    camera app at the sticker and have it open -- no app install, no in-app
    scanner required. The in-app scanner is a convenience, not a prerequisite.
    """
    return f"{base_url.rstrip('/')}/stall/{normalize_code(code)}"


def clamp_box_size(size: Optional[int]) -> int:
    """Bound the requested render size.

    Unbounded, `?size=100000` would have the server build a multi-gigabyte
    bitmap on an unauthenticated-ish route -- a trivial denial of service.
    """
    if size is None:
        return _DEFAULT_BOX_SIZE
    return max(_MIN_BOX_SIZE, min(_MAX_BOX_SIZE, int(size)))


def render_png(payload: str, box_size: Optional[int] = None) -> bytes:
    """Render `payload` as a PNG QR code.

    Pure: a string in, bytes out. No database, no settings, no I/O -- so the
    path a vendor's printed sticker depends on is testable in isolation.
    """
    qr = qrcode.QRCode(
        version=None,  # fit to the payload
        error_correction=_ERROR_CORRECTION,
        box_size=clamp_box_size(box_size),
        border=_BORDER_MODULES,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def png_dimensions(box_size: Optional[int] = None, modules: int = 29) -> int:
    """Expected pixel width, for tests and for sizing the vendor screen.

    `modules` defaults to the module count of a short URL payload, which is
    what every real code here encodes.
    """
    return (modules + 2 * _BORDER_MODULES) * clamp_box_size(box_size)
