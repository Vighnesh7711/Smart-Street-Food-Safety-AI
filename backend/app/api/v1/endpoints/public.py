"""Public, unauthenticated endpoints.

This router has no `Depends(get_current_user)` anywhere, by design. It is the
only surface in the API reachable without a token, so anything added here is
published to the world -- see schemas/public.py for what may appear.

Responses are deliberately uniform: an unknown code and a revoked code both
produce a byte-identical 404, so the endpoint cannot be used to test whether
a particular stall ever existed.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.public import PublicStallProfile
from app.services.public import service as public_service

router = APIRouter()

#: Short shared cache. The data is public and non-personal, so a shared cache
#: is appropriate, and 60 seconds meaningfully blunts scripted scraping of
#: the code space without making the page feel stale to a consumer standing
#: at the stall.
_PUBLIC_CACHE_SECONDS = 60

#: Identical for "no such code" and "code revoked". Both are 404 with the
#: same body, so the response cannot be used to probe for existence.
_NOT_FOUND_DETAIL: dict[str, Any] = {
    "detail": "No stall found for that code.",
    "code": "stall_not_found",
}


@router.get(
    "/stalls/{code}",
    response_model=PublicStallProfile,
    summary="Public stall profile (no authentication)",
)
def read_public_stall(
    code: str,
    response: Response,
    db: Session = Depends(get_db),
) -> PublicStallProfile:
    """Everything the public stall page shows, and nothing else.

    `code` is the stall's random QR code, not its serial id -- a serial id
    would let anyone walk the id space and scrape every stall's score.
    """
    profile = public_service.get_by_code(db, code)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL
        )

    response.headers["Cache-Control"] = f"public, max-age={_PUBLIC_CACHE_SECONDS}"
    return profile
