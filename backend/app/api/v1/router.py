"""Aggregates every v1 router.

`main.py` includes exactly one router (this one). Adding a resource means
adding a module under endpoints/ and one line here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    hygiene,
    ingredients,
    products,
    public,
    reviewer,
    stalls,
    vendors,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
api_router.include_router(stalls.router, prefix="/stalls", tags=["stalls"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(hygiene.router, prefix="/hygiene", tags=["hygiene"])
api_router.include_router(
    ingredients.router, prefix="/ingredients", tags=["ingredients"]
)
# Reviewer-only. Role enforcement lives on the router itself, so a route
# added to that module cannot be left ungated by accident.
api_router.include_router(reviewer.router, prefix="/reviewer", tags=["reviewer"])
# Unauthenticated. Kept last and in its own module so it is obvious at a
# glance which surface of the API has no auth dependency.
api_router.include_router(public.router, prefix="/public", tags=["public"])

# Exposed for tests that want the resolved prefix without importing settings.
API_V1_STR = settings.API_V1_STR
