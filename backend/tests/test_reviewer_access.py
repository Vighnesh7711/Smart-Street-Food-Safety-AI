"""Reviewer access control.

Every /reviewer/* route must reject vendors and consumers. This is asserted
route by route rather than by spot-checking, because the failure mode of
per-route gating is exactly that someone adds a route and forgets.
"""

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.db.session import get_db
from app.main import app
from app.models.enums import FlagStatus, UserRole
from app.models.user import User

#: Every reviewer route, with a method and (where needed) a body. Kept as data
#: so a new route is a one-line addition to this list rather than a new test.
ROUTES = [
    ("GET", "/api/v1/reviewer/vendors", None),
    ("GET", "/api/v1/reviewer/summary", None),
    ("GET", "/api/v1/reviewer/flags", None),
    ("GET", "/api/v1/reviewer/vendors/1", None),
    ("POST", "/api/v1/reviewer/vendors/1/flags", {"reason": "Test reason"}),
    ("POST", "/api/v1/reviewer/flags/1/resolve", {}),
]


@pytest.fixture
def world(reviewer_world):
    db, reviewer, stalls = reviewer_world()
    app.dependency_overrides[get_db] = lambda: (yield db)
    with TestClient(app) as client:
        yield client, db, reviewer, stalls
    app.dependency_overrides.clear()


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


def _call(client, method: str, path: str, body, headers):
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body or {}, headers=headers)


class TestRoleEnforcement:
    @pytest.mark.parametrize("method,path,body", ROUTES)
    def test_anonymous_is_rejected(self, world, method, path, body):
        client, *_ = world
        assert _call(client, method, path, body, {}).status_code == 401

    @pytest.mark.parametrize("method,path,body", ROUTES)
    def test_vendor_is_rejected(self, world, method, path, body):
        """A vendor must not be able to read the register or flag anyone."""
        client, db, _, _ = world
        vendor = User(
            email="vendor@example.test", hashed_password="x", role=UserRole.VENDOR
        )
        db.add(vendor)
        db.commit()

        response = _call(client, method, path, body, _headers(vendor))
        assert response.status_code == 403

    @pytest.mark.parametrize("method,path,body", ROUTES)
    def test_consumer_is_rejected(self, world, method, path, body):
        client, db, _, _ = world
        consumer = User(
            email="consumer@example.test", hashed_password="x", role=UserRole.CONSUMER
        )
        db.add(consumer)
        db.commit()

        response = _call(client, method, path, body, _headers(consumer))
        assert response.status_code == 403

    def test_reviewer_is_allowed_on_the_table(self, world):
        client, _, reviewer, _ = world
        assert (
            client.get("/api/v1/reviewer/vendors", headers=_headers(reviewer)).status_code
            == 200
        )

    def test_admin_is_allowed(self, world):
        client, db, _, _ = world
        admin = User(
            email="admin@example.test", hashed_password="x", role=UserRole.ADMIN
        )
        db.add(admin)
        db.commit()
        assert (
            client.get("/api/v1/reviewer/vendors", headers=_headers(admin)).status_code
            == 200
        )

    def test_a_missing_route_is_404_not_403(self, world):
        """Distinguishes "no such endpoint" from "not allowed", so a typo in
        a client is diagnosable."""
        client, _, reviewer, _ = world
        assert (
            client.get("/api/v1/reviewer/nonexistent", headers=_headers(reviewer)).status_code
            == 404
        )


class TestPublicRouteIsUnaffected:
    def test_public_still_needs_no_token(self, world):
        """Regression guard: adding router-level auth must not have leaked
        onto the unauthenticated public router."""
        client, *_ = world
        # 404 because the code is unknown -- but NOT 401, which would mean
        # auth got applied where it should not.
        assert client.get("/api/v1/public/stalls/ZZZZZZZZZZ").status_code == 404
