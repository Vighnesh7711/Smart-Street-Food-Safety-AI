"""Vendors table: filters, sorting, pagination, and query behaviour."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core import security
from app.db.session import get_db
from app.main import app
from app.models.enums import CheckStatus, ScanStatus, UserRole
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_score import HygieneScore
from app.models.product import Product
from app.models.stall import Stall
from app.models.user import User
from app.models.vendor import Vendor


@contextmanager
def count_queries(db):
    """Count SQL statements issued through this session's engine."""
    statements = []

    def before(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


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


def fetch(client, headers, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url = "/api/v1/reviewer/vendors" + (f"?{query}" if query else "")
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def names(payload):
    return sorted(item["stall_name"] for item in payload["items"])


class TestListing:
    def test_returns_every_stall_with_its_total(self, world):
        client, _, _, _, headers = world
        body = fetch(client, headers)
        assert body["total"] == 4
        assert len(body["items"]) == 4

    def test_row_shape_matches_the_table_columns(self, world):
        client, _, _, _, headers = world
        row = next(
            item
            for item in fetch(client, headers)["items"]
            if item["stall_name"] == "Ramesh Vada Pav"
        )
        assert row["latest_score"] == 92.0
        assert row["band"] == "good"
        assert row["latest_scan_status"] == "Suitable"
        assert row["vendor_name"] == "Ramesh Kumar"
        assert row["has_open_flag"] is False

    def test_unassessed_stall_has_no_band(self, world):
        """Not "bad" -- an unassessed stall must not read as the worst
        performer."""
        client, _, _, _, headers = world
        row = next(
            item
            for item in fetch(client, headers)["items"]
            if item["stall_name"] == "New Stall"
        )
        assert row["latest_score"] is None
        assert row["band"] is None
        assert row["latest_scan_status"] is None

    def test_latest_score_wins_when_there_are_several(self, world):
        client, _, _, _, headers = world
        row = next(
            item
            for item in fetch(client, headers)["items"]
            if item["stall_name"] == "Ramesh Vada Pav"
        )
        # Two assessments: 88 then 92.
        assert row["latest_score"] == 92.0


class TestFilters:
    def test_filter_by_band(self, world):
        client, _, _, _, headers = world
        assert names(fetch(client, headers, band="good")) == ["Ramesh Vada Pav"]
        assert names(fetch(client, headers, band="fair")) == ["Anita Chaat"]
        assert names(fetch(client, headers, band="bad")) == ["Biryani Corner"]

    def test_filter_by_none_band(self, world):
        """'Never assessed' is a filter a reviewer actually wants."""
        client, _, _, _, headers = world
        assert names(fetch(client, headers, band="none")) == ["New Stall"]

    def test_unknown_band_matches_nothing(self, world):
        """Silently ignoring an unrecognised filter would show every stall to
        a reviewer who asked for a specific one."""
        client, _, _, _, headers = world
        assert fetch(client, headers, band="bogus")["total"] == 0

    def test_filter_flagged(self, world):
        client, _, _, _, headers = world
        assert names(fetch(client, headers, flagged="true")) == ["Anita Chaat"]
        unflagged = names(fetch(client, headers, flagged="false"))
        assert "Anita Chaat" not in unflagged
        assert len(unflagged) == 3

    def test_filter_has_scan(self, world):
        client, _, _, _, headers = world
        with_scans = names(fetch(client, headers, has_scan="true"))
        assert with_scans == ["Anita Chaat", "Ramesh Vada Pav"]
        without = names(fetch(client, headers, has_scan="false"))
        assert without == ["Biryani Corner", "New Stall"]

    def test_search_matches_stall_name(self, world):
        client, _, _, _, headers = world
        assert names(fetch(client, headers, search="vada")) == ["Ramesh Vada Pav"]

    def test_search_matches_vendor_name(self, world):
        """A reviewer looking for "Imran" should find his stall whether they
        know the stall's name or his."""
        client, _, _, _, headers = world
        assert names(fetch(client, headers, search="Imran")) == ["Biryani Corner"]

    def test_search_is_case_insensitive(self, world):
        client, _, _, _, headers = world
        assert names(fetch(client, headers, search="ANITA")) == ["Anita Chaat"]

    def test_filters_combine(self, world):
        client, _, _, _, headers = world
        assert fetch(client, headers, flagged="true", has_scan="true")["total"] == 1
        assert fetch(client, headers, flagged="true", band="bad")["total"] == 0

    def test_omitting_flagged_is_not_the_same_as_false(self, world):
        """`flagged=false` filters to unflagged; omitting it means no filter."""
        client, _, _, _, headers = world
        assert fetch(client, headers)["total"] == 4
        assert fetch(client, headers, flagged="false")["total"] == 3


class TestSorting:
    def test_sort_by_name_ascending(self, world):
        client, _, _, _, headers = world
        body = fetch(client, headers, sort="stall_name", order="asc")
        assert [i["stall_name"] for i in body["items"]] == sorted(
            i["stall_name"] for i in body["items"]
        )

    def test_sort_by_score_descending(self, world):
        client, _, _, _, headers = world
        scores = [
            i["latest_score"]
            for i in fetch(client, headers, sort="hygiene", order="desc")["items"]
            if i["latest_score"] is not None
        ]
        assert scores == sorted(scores, reverse=True)

    def test_unassessed_sorts_last_in_both_directions(self, world):
        """A stall with no score must not masquerade as the worst performer
        by appearing first in a worst-first list."""
        client, _, _, _, headers = world
        ascending = fetch(client, headers, sort="hygiene", order="asc")["items"]
        descending = fetch(client, headers, sort="hygiene", order="desc")["items"]
        assert ascending[-1]["stall_name"] == "New Stall"
        assert descending[-1]["stall_name"] == "New Stall"

    def test_sort_by_last_activity(self, world):
        client, _, _, _, headers = world
        body = fetch(client, headers, sort="last_activity", order="desc")
        dates = [i["last_activity_at"] for i in body["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_rejects_an_unknown_sort_key(self, world):
        """The sort key reaches an ORDER BY, so it is a closed set rather
        than a free string."""
        client, _, _, _, headers = world
        response = client.get(
            "/api/v1/reviewer/vendors?sort=;DROP TABLE stalls--", headers=headers
        )
        assert response.status_code == 422


class TestPagination:
    def test_limit_and_total(self, world):
        client, _, _, _, headers = world
        body = fetch(client, headers, limit=2)
        assert len(body["items"]) == 2
        # The total is the unpaginated count, so the UI can say "of 4".
        assert body["total"] == 4

    def test_skip_pages(self, world):
        client, _, _, _, headers = world
        first = fetch(client, headers, limit=2, skip=0, sort="stall_name", order="asc")
        second = fetch(client, headers, limit=2, skip=2, sort="stall_name", order="asc")
        assert not (
            {i["stall_id"] for i in first["items"]}
            & {i["stall_id"] for i in second["items"]}
        )

    def test_pages_cover_every_row_exactly_once(self, world):
        """Stable ordering matters: without a tie-break, two stalls with the
        same score can swap between pages and one is silently skipped."""
        client, _, _, _, headers = world
        seen = []
        for page in range(2):
            body = fetch(
                client, headers, limit=2, skip=page * 2, sort="hygiene", order="desc"
            )
            seen.extend(i["stall_id"] for i in body["items"])
        assert sorted(seen) == sorted({i for i in seen})
        assert len(seen) == 4

    def test_limit_is_bounded(self, world):
        client, _, _, _, headers = world
        assert (
            client.get(
                "/api/v1/reviewer/vendors?limit=99999", headers=headers
            ).status_code
            == 422
        )

    def test_filters_apply_to_the_total_not_just_the_page(self, world):
        client, _, _, _, headers = world
        body = fetch(client, headers, band="none", limit=1)
        assert body["total"] == 1


class TestQueryBehaviour:
    """The N+1 guard.

    Each row needs a latest score, a latest scan, and a flag count from three
    different tables. The obvious implementation is three queries per row;
    an N+1 here is invisible on seed data and painful on a real register.
    """

    def test_query_count_does_not_grow_with_row_count(self, world):
        client, db, reviewer, _, headers = world

        with count_queries(db) as small:
            fetch(client, headers, limit=2)

        # Add more stalls and re-run the same shape of request.
        vendor = db.query(Vendor).first()
        now = datetime.now(timezone.utc)
        for index in range(20):
            stall = Stall(
                vendor_id=vendor.id,
                name=f"Bulk Stall {index}",
                created_at=now - timedelta(days=index),
            )
            db.add(stall)
            db.commit()
            check = HygieneCheck(
                stall_id=stall.id,
                status=CheckStatus.SCORED.value,
                coverage_ok=True,
            )
            db.add(check)
            db.flush()
            db.add(
                HygieneScore(
                    hygiene_check_id=check.id,
                    visual_score=50.0,
                    final_score=50.0,
                    breakdown={},
                    weights={},
                    formula_version="v1",
                )
            )
            db.add(Product(stall_id=stall.id, status=ScanStatus.SUITABLE.value))
            db.commit()

        with count_queries(db) as large:
            fetch(client, headers, limit=25)

        # 24 stalls vs 4. A bounded constant here is the whole point: the
        # absolute number may shift slightly with SQLAlchemy internals, but
        # it must not scale with rows.
        assert len(large) <= len(small) + 4, (
            f"query count grew from {len(small)} to {len(large)} "
            "when the row count grew -- this is an N+1"
        )

    def test_summary_is_bounded_too(self, world):
        client, db, _, _, headers = world
        with count_queries(db) as statements:
            assert client.get("/api/v1/reviewer/summary", headers=headers).status_code == 200
        assert len(statements) <= 4


class TestSummary:
    def test_headline_numbers(self, world):
        client, _, _, _, headers = world
        body = client.get("/api/v1/reviewer/summary", headers=headers).json()

        assert body["total_stalls"] == 4
        assert body["assessed_stalls"] == 3
        assert body["flagged_stalls"] == 1
        assert body["bands"]["good"] == 1
        assert body["bands"]["fair"] == 1
        assert body["bands"]["bad"] == 1
        assert body["bands"]["none"] == 1

    def test_average_ignores_unassessed_stalls(self, world):
        client, _, _, _, headers = world
        body = client.get("/api/v1/reviewer/summary", headers=headers).json()
        # (92 + 63.5 + 30) / 3, not divided by 4.
        assert body["average_score"] == pytest.approx((92.0 + 63.5 + 30.0) / 3)

    def test_average_is_null_when_nothing_is_assessed(self, world):
        client, db, _, _, headers = world
        db.query(HygieneScore).delete()
        db.commit()
        body = client.get("/api/v1/reviewer/summary", headers=headers).json()
        assert body["average_score"] is None
        assert body["assessed_stalls"] == 0
