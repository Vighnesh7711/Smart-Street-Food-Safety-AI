"""Flag lifecycle: create, list, resolve."""

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.db.session import get_db
from app.main import app
from app.models.enums import FlagStatus, UserRole
from app.models.flag import Flag
from app.models.user import User


@pytest.fixture
def world(reviewer_world):
    db, reviewer, stalls = reviewer_world()
    app.dependency_overrides[get_db] = lambda: (yield db)
    with TestClient(app) as client:
        headers = {
            "Authorization": f"Bearer {security.create_access_token(reviewer.id)}"
        }
        yield client, db, reviewer, stalls, headers
    app.dependency_overrides.clear()


def create_flag(client, headers, stall_id, reason="Waste water beside prep table"):
    return client.post(
        f"/api/v1/reviewer/vendors/{stall_id}/flags",
        json={"reason": reason},
        headers=headers,
    )


class TestCreating:
    def test_creates_an_open_flag(self, world):
        client, _, reviewer, stalls, headers = world
        response = create_flag(client, headers, stalls["poor"].id)

        assert response.status_code == 201
        body = response.json()
        assert body["reason"] == "Waste water beside prep table"
        assert body["status"] == "open"
        assert body["created_by_name"] == "Priya Officer"
        assert body["created_at"] is not None

    def test_the_reason_is_required(self, world):
        client, _, _, stalls, headers = world
        response = client.post(
            f"/api/v1/reviewer/vendors/{stalls['poor'].id}/flags",
            json={},
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("reason", ["", "  ", "ab", "\n\t "])
    def test_a_blank_or_too_short_reason_is_rejected(self, world, reason):
        """A flag with no reason is not actionable by whoever picks it up,
        which defeats the point of recording it."""
        client, _, _, stalls, headers = world
        assert create_flag(client, headers, stalls["poor"].id, reason).status_code == 422

    def test_a_reason_is_trimmed(self, world):
        client, _, _, stalls, headers = world
        body = create_flag(client, headers, stalls["poor"].id, "  Spilled oil  ").json()
        assert body["reason"] == "Spilled oil"

    def test_an_overlong_reason_is_rejected(self, world):
        client, _, _, stalls, headers = world
        assert create_flag(client, headers, stalls["poor"].id, "x" * 501).status_code == 422

    def test_flagging_an_unknown_stall_is_404(self, world):
        client, _, _, _, headers = world
        assert create_flag(client, headers, 99999).status_code == 404

    def test_two_reviewers_can_flag_the_same_stall(self, world):
        """Two reviewers noticing two different problems should both be
        recorded, not deduplicated."""
        client, db, _, stalls, headers = world
        create_flag(client, headers, stalls["poor"].id, "Waste water pooling")

        other = User(
            email="second@example.test",
            hashed_password="x",
            role=UserRole.REVIEWER,
            full_name="Second Officer",
        )
        db.add(other)
        db.commit()
        other_headers = {
            "Authorization": f"Bearer {security.create_access_token(other.id)}"
        }
        create_flag(client, other_headers, stalls["poor"].id, "Uncovered food on counter")

        body = client.get("/api/v1/reviewer/flags", headers=headers).json()
        on_that_stall = [f for f in body["items"] if f["stall_id"] == stalls["poor"].id]
        assert len(on_that_stall) == 2

    def test_the_stall_row_reflects_the_flag(self, world):
        client, _, _, stalls, headers = world
        create_flag(client, headers, stalls["poor"].id)

        rows = client.get("/api/v1/reviewer/vendors", headers=headers).json()["items"]
        row = next(r for r in rows if r["stall_id"] == stalls["poor"].id)
        assert row["has_open_flag"] is True
        assert row["open_flag_count"] == 1


class TestListing:
    def test_defaults_to_open_flags(self, world):
        """Omitting `status` means open, not all -- a flagged list that
        silently includes resolved history is not a to-do list."""
        client, _, _, stalls, headers = world
        body = client.get("/api/v1/reviewer/flags", headers=headers).json()

        assert body["total"] == 1  # the fixture's pre-existing open flag
        assert all(item["status"] == "open" for item in body["items"])

    def test_includes_the_stall_name(self, world):
        client, _, _, _, headers = world
        body = client.get("/api/v1/reviewer/flags", headers=headers).json()
        assert body["items"][0]["stall_name"] == "Anita Chaat"

    def test_newest_first(self, world):
        client, _, _, stalls, headers = world
        create_flag(client, headers, stalls["poor"].id)
        body = client.get("/api/v1/reviewer/flags", headers=headers).json()
        dates = [item["created_at"] for item in body["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_resolved_filter(self, world):
        client, _, _, _, headers = world
        body = client.get(
            "/api/v1/reviewer/flags?status=resolved", headers=headers
        ).json()
        assert body["total"] == 0


class TestResolving:
    def test_resolve_records_who_and_when(self, world):
        client, db, reviewer, stalls, headers = world
        flag = create_flag(client, headers, stalls["poor"].id).json()

        response = client.post(
            f"/api/v1/reviewer/flags/{flag['id']}/resolve",
            json={"note": "Visited on 18 Sep, cleared"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "resolved"
        assert body["resolved_by_name"] == "Priya Officer"
        assert body["resolved_at"] is not None
        assert body["resolution_note"] == "Visited on 18 Sep, cleared"

    def test_resolving_without_a_note_is_allowed(self, world):
        client, _, _, stalls, headers = world
        flag = create_flag(client, headers, stalls["poor"].id).json()
        body = client.post(
            f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers
        ).json()
        assert body["status"] == "resolved"
        assert body["resolution_note"] is None

    def test_resolving_twice_is_rejected(self, world):
        """Overwriting `resolved_by` would destroy the record of who actually
        dealt with it, which is the only reason the field exists."""
        client, _, _, stalls, headers = world
        flag = create_flag(client, headers, stalls["poor"].id).json()
        client.post(f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers)

        second = client.post(
            f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers
        )
        assert second.status_code == 422

    def test_resolving_an_unknown_flag_is_404(self, world):
        client, _, _, _, headers = world
        assert (
            client.post(
                "/api/v1/reviewer/flags/99999/resolve", json={}, headers=headers
            ).status_code
            == 404
        )

    def test_resolved_flags_leave_the_open_list(self, world):
        client, _, _, stalls, headers = world
        create_flag(client, headers, stalls["poor"].id)
        before = client.get("/api/v1/reviewer/flags", headers=headers).json()["total"]

        flag = client.get("/api/v1/reviewer/flags", headers=headers).json()["items"][0]
        client.post(f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers)

        after = client.get("/api/v1/reviewer/flags", headers=headers).json()
        assert after["total"] == before - 1
        resolved = client.get(
            "/api/v1/reviewer/flags?status=resolved", headers=headers
        ).json()
        assert resolved["total"] == 1

    def test_the_stall_row_clears_after_resolution(self, world):
        client, _, _, stalls, headers = world
        flag = create_flag(client, headers, stalls["poor"].id).json()
        client.post(f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers)

        rows = client.get("/api/v1/reviewer/vendors", headers=headers).json()["items"]
        row = next(r for r in rows if r["stall_id"] == stalls["poor"].id)
        assert row["has_open_flag"] is False

    def test_the_flagged_filter_tracks_resolution(self, world):
        client, _, _, stalls, headers = world

        def flagged_count():
            return client.get(
                "/api/v1/reviewer/vendors?flagged=true", headers=headers
            ).json()["total"]

        # The fixture's pre-existing flag on Anita Chaat.
        assert flagged_count() == 1

        create_flag(client, headers, stalls["poor"].id)
        assert flagged_count() == 2

        anita_flag = next(
            f
            for f in client.get("/api/v1/reviewer/flags", headers=headers).json()["items"]
            if f["stall_name"] == "Anita Chaat"
        )
        client.post(
            f"/api/v1/reviewer/flags/{anita_flag['id']}/resolve", json={}, headers=headers
        )
        # Anita drops off; the newly flagged stall stays.
        assert flagged_count() == 1


class TestStallDetailFlags:
    def test_open_flags_appear_on_the_detail(self, world):
        client, _, _, stalls, headers = world
        detail = client.get(
            f"/api/v1/reviewer/vendors/{stalls['flagged'].id}", headers=headers
        ).json()
        assert len(detail["open_flags"]) == 1
        assert detail["open_flags"][0]["reason"] == "Prep area unswept"

    def test_resolved_flags_do_not_appear_on_the_detail(self, world):
        client, _, _, stalls, headers = world
        flag = client.get("/api/v1/reviewer/flags", headers=headers).json()["items"][0]
        client.post(f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers)

        detail = client.get(
            f"/api/v1/reviewer/vendors/{stalls['flagged'].id}", headers=headers
        ).json()
        assert detail["open_flags"] == []


class TestFlagPersistence:
    def test_flag_rows_cascade_from_stalls_at_the_database_level(self, world):
        """Flags carry ON DELETE CASCADE, so removing a stall cannot leave
        flag rows pointing at something that no longer exists.

        Asserted against the declared constraint rather than by deleting a
        stall. Deleting a stall is not a feature in this phase, and an ORM
        delete would in any case fail earlier -- on `hygiene_checks`, whose
        relationship has no cascade configured. That is a real gap, but it
        belongs to whichever phase introduces stall deletion; adding
        cascades across four relationships to satisfy a test for an
        operation nobody can perform yet would be the wrong shape.

        SQLite does not enforce foreign keys unless the pragma is on, so
        this checks the schema declaration, which is what PostgreSQL acts on.
        """
        from app.models.flag import Flag

        stall_fk = next(
            fk
            for fk in Flag.__table__.foreign_keys
            if fk.column.table.name == "stalls"
        )
        assert stall_fk.ondelete == "CASCADE"

    def test_resolving_does_not_delete_the_flag(self, world):
        """Resolved flags are history, not garbage -- the record of who
        dealt with something is the point of keeping them."""
        client, db, _, stalls, headers = world
        flag = create_flag(client, headers, stalls["poor"].id).json()
        client.post(f"/api/v1/reviewer/flags/{flag['id']}/resolve", json={}, headers=headers)

        assert db.query(Flag).filter(Flag.id == flag["id"]).count() == 1
