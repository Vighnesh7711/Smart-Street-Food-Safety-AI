# Implementation Plan — Phase 5: Reviewer Dashboard

Status: **IMPLEMENTED** — see "Deltas from this plan" immediately below for
where the built system diverges from what was approved.

Builds on: Phases 1–4.

---

## Deltas from this plan

### `stalls.is_flagged` was dropped, as proposed

Confirmed by inspection rather than assumption: **nothing in the codebase
ever wrote to it**, and `StallRead` serialized it as `false` forever. The API
field is replaced by `has_open_flag`, derived from the `flags` table. Three
files changed, no test referenced it.

### Bugs found while building

| # | Problem | Resolution |
|---|---|---|
| 1 | **An unassessed stall displayed band `"bad"`** — a NULL score falls through every `CASE WHEN` comparison (`NULL >= 80` is NULL, not false) and lands on `else_`. It would have shown as the worst performer and sorted to the top of a worst-first list | Explicit `IS NULL` branch in the band CASE. "No data" is not "bad data" |
| 2 | `band=bad` returned **zero rows** — the filter had a dead branch that treated the lowest band as "handled separately", which the caller never did | Filter now compares against the computed band column itself, so the filter cannot disagree with the value displayed |
| 3 | **Flagging a non-existent stall returned 500**, not 404 — `create_flag` did not catch `ReviewerError` | Both stall-scoped endpoints now translate it |
| 4 | `GREATEST()` and `INTERVAL '7 days'` are PostgreSQL-only, and the tests run on SQLite | Rewritten as a portable `CASE` and a Python-computed cutoff |
| 5 | `order_by="desc(Flag.created_at)"` on a relationship — the string evaluates in a namespace holding mapped classes, not SQLAlchemy functions | `"Flag.created_at.desc()"` |
| 6 | Importing `models/stall.py` alone left `Flag` unregistered, so any test importing just the models it needs failed at mapper configuration | Explicit import with a comment on why it must stay |

Bug 1 is the one worth dwelling on: it is a data-modelling error that
produces a plausible-looking number rather than an exception, in a tool whose
entire job is telling a reviewer which stalls need attention.

### Test bugs that were mine, not the code's

- The fixture built score lists oldest-*last*, so "latest score" returned the
  first entry. Fixed to read chronologically.
- `ProductIngredient` rows with duplicate `(product_id, ingredient_id)` hit a
  real unique constraint — by design, from Phase 2.
- A stall-deletion cascade test failed on `hygiene_checks.stall_id`. The
  finding is real: **`Stall.hygiene_checks` has no cascade configured**, so
  deleting a stall would fail. Stall deletion is not a feature in this phase,
  so the test was rewritten to assert the FK constraint that actually
  protects the data, and the gap is recorded here rather than papered over.

### Additions beyond the approved plan

1. **A KPI row** (`GET /reviewer/summary`) — the visualization method calls
   for stat tiles when a dashboard leads with headline numbers, and a
   reviewer landing on a bare table has no sense of scale.
2. **`resolve` on the vendor detail page**, not only the flagged list — a
   reviewer reading a stall's history is exactly where they decide it is
   dealt with.
3. **A `SignOutButton`** for the desktop shell. The button existed since
   Phase 1 and did nothing. Note it clears the cookie client-side only; the
   JWT stays valid until expiry, so real revocation needs a denylist
   (deferred with the audit-logging work).
4. **Control-character-safe sort keys** — `sort` is a closed enum rather than
   a free string, because the value reaches an `ORDER BY`.
5. **The report-follow-up gap noted for stall deletion** (see above).

### Where the build differs from the plan's structure

- The score chart lives in `lib/chartScale.ts` (pure geometry) plus
  `components/reviewer/HygieneScoreChart.tsx`, rather than one file. The
  split is what makes the degenerate-case tests possible.
- `StatusPill.tsx` exports `HygieneStatus`, `ScanStatusPill`, `FlagBadge`,
  and `ScoreDelta` — one module so "colour is never the only signal" is
  enforced by the component rather than by convention.
- `reviewerApi.ts` is separate from `api.ts`, built on an exported
  `apiRequest`, so the reviewer surface does not bloat the vendor client.

### Verification status

- **490 backend tests pass**, up from 394. **41 frontend tests pass.**
- Migrations match all 16 models exactly.
- Frontend: `tsc --noEmit` clean, `next build` succeeds (16 routes).
- The query-count test asserts the vendors table issues a **bounded** number
  of queries independent of row count.
- **Not verified against live services.** Same caveat as Phases 2–4: no
  PostgreSQL was reachable, so migration 0005 is validated by construction.
  The dashboard has never been opened against a real backend with real data —
  layout, label collisions, and long-name overflow are the things that only
  show up when you look at it.

---

## 1. Decisions locked (from your answers)

1. **A row per stall**, showing the owning vendor's name. Every column maps
   1:1 to a row, and each stall sorts on its own record. A two-stall vendor
   appears twice — correct, since the columns are stall-level.
2. **Hand-rolled SVG** for the score chart. No new dependency.
3. **Flags have an open/resolved lifecycle**, with `resolved_by` and
   `resolved_at` recorded. The flagged view shows open flags by default with
   a toggle for history.

---

## 2. `stalls.is_flagged` should go

Phase 1 added `stalls.is_flagged` (0/1). I checked: **nothing writes it.**
It is read only by `StallRead`, which always serializes `false`.

Flags are now much richer — reason, reviewer, timestamp, resolution — so that
boolean would become a second, unmaintained source of truth for "is this
flagged", free to drift from the `flags` table. Same reasoning as
`stalls.qr_code_id` in Phase 4, and the same fix: drop the column, derive the
answer from the table that actually holds it.

Blast radius, measured: `models/stall.py`, `schemas/stall.py` (field +
coercion validator), `frontend/src/lib/types.ts`. Three files, no test
references, no data (the database has never been created).

I'll keep proposing this until you tell me to stop, but it's the last one —
this was the only remaining dead denormalization I know of.

---

## 3. Folder structure (Phase 5 additions)

```
backend/
├── alembic/versions/
│   └── 0005_phase5_reviewer.py     # NEW — flags table; drop stalls.is_flagged
└── app/
    ├── models/
    │   ├── enums.py                # UPDATED — FlagStatus
    │   ├── flag.py                 # NEW — Flag
    │   └── stall.py                # UPDATED — drop is_flagged, add relationship
    ├── schemas/
    │   ├── reviewer.py             # NEW — table rows, detail, flags, summary
    │   └── stall.py                # UPDATED
    ├── crud/
    │   ├── flag.py                 # NEW
    │   └── reviewer.py             # NEW — the aggregate queries
    ├── services/
    │   └── reviewer/service.py     # NEW — flag lifecycle, detail assembly
    └── api/v1/endpoints/
        └── reviewer.py             # NEW — the /reviewer/* set

frontend/src/
├── app/(desktop)/reviewer/
│   ├── page.tsx                    # REWRITTEN — was mock data
│   ├── layout.tsx                  # UPDATED — refresh + new nav
│   ├── [stallId]/page.tsx          # NEW — vendor detail
│   └── flagged/page.tsx            # NEW — flagged list
├── components/reviewer/
│   ├── VendorsTable.tsx            # NEW
│   ├── HygieneScoreChart.tsx       # NEW — hand-rolled SVG
│   ├── ScanHistoryTable.tsx        # NEW
│   ├── StallImageGallery.tsx       # NEW — detection overlay
│   ├── FlagDialog.tsx              # NEW
│   └── StatusPill.tsx              # NEW — status colour + icon + label
└── lib/reviewerApi.ts              # NEW — typed calls for /reviewer/*
```

---

## 4. Data model

**`flags`**

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `stall_id` | FK stalls, indexed | Per your Q1 decision — one row per stall |
| `reason` | String(500), NOT NULL | Required, short. Enforced non-blank server-side |
| `status` | String(20), indexed | `open` / `resolved` |
| `created_by_user_id` | FK users, indexed | The reviewer |
| `created_at` | timestamptz, indexed | |
| `resolved_by_user_id` | FK users, nullable | |
| `resolved_at` | timestamptz, nullable | |
| `resolution_note` | String(500), nullable | Optional "what was done" |

Plus a **partial index** on open flags:

```sql
CREATE INDEX ix_flags_open ON flags (stall_id) WHERE status = 'open';
```

Same technique as `qr_codes`' one-active-per-stall index: the query the
dashboard actually runs is "which stalls are currently flagged", and a
partial index keeps that cheap no matter how much closed history accumulates.

**What is deliberately absent:** officer assignment, priority/severity,
due dates, notifications, attachments. Your scope is read/monitor/flag, and
each of those would drag in decisions (who is assignable? what makes something
urgent?) that belong in a later phase.

---

## 5. API surface

All under `/api/v1/reviewer`, gated by
`require_roles(UserRole.REVIEWER, UserRole.ADMIN)` — the same dependency
factory the other protected routes use, so role enforcement stays in one place.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/reviewer/vendors` | The table: filter, sort, paginate |
| `GET` | `/reviewer/vendors/{stall_id}` | Detail: score history, scan history, images |
| `GET` | `/reviewer/summary` | KPI row numbers |
| `GET` | `/reviewer/flags` | Flag list (`status` filter) |
| `POST` | `/reviewer/vendors/{stall_id}/flags` | Raise a flag (required reason) |
| `POST` | `/reviewer/flags/{flag_id}/resolve` | Resolve with an optional note |

### Filtering and sorting happen on the server

`GET /reviewer/vendors` accepts `search`, `flagged`, `band`, `has_scan`,
`sort`, `order`, `skip`, `limit`, and returns `{items, total}`.

Not a client-side convenience detail — it is a correctness requirement. If the
page fetched 200 stalls and filtered in the browser, a reviewer filtering for
"flagged" would silently miss a flagged stall at position 201, in the one tool
whose entire job is finding the stalls that need attention. Same for sort:
sorting one page of a paginated list produces a wrong-looking order.

### The aggregate query must not be N+1

Each row needs the stall's **latest hygiene score**, **latest scan status**,
and **last activity date**. The obvious implementation issues three queries
per row — 600 for a 200-row page.

Instead: **one** query using `ROW_NUMBER() OVER (PARTITION BY stall_id ORDER
BY ...)` subqueries joined to `stalls`, with filters and sort applied in the
same statement. I'll assert the query count in a test, because an N+1 here is
invisible on seed data and painful at scale.

Sorting by "latest hygiene score" also sorts on a **derived** column, which is
the other reason this cannot be done client-side.

---

## 6. Frontend

### Vendors table (`/reviewer`)

Columns: stall name · category · hygiene status · last scan · last activity ·
flag action. Row click opens the detail page.

- **Sortable** on name, hygiene, last activity — server-side, so sorting is
  over the whole result set rather than the current page.
- **Filters in one row above the table** (search, band, flagged-only,
  has-scan), per the dataviz interaction guidance.
- **Pagination** with a visible total, so a reviewer knows whether they are
  looking at 12 stalls or 1,200.

### Hygiene status rendering — the accessibility rule

Hygiene band is a **status**, so it renders as **colour + icon + label**,
never colour alone. Two of the four status colours are below 3:1 contrast on
a light surface by design, so the icon and the text are what carry the
meaning; the colour is reinforcement.

This also applies to the Phase 3 mobile history cards, which currently
colour-band the score number without a label. I'd like to backport it there —
small change, same reason.

### Vendor detail (`/reviewer/[stallId]`)

- **Hero stat tile**: current score, band, delta since the previous check.
  A single current value is a stat tile, not a chart.
- **Score history chart**: line + visible point markers. Markers matter —
  hygiene checks are *discrete assessments*, and a bare line implies
  continuous measurement between them. A reference line at the "needs work"
  boundary (60) makes crossing it legible.
- **Scan history table**: status, language, confidence, date.
- **Stall image gallery**: each submitted photo with its detected indicators
  **listed** beneath it, and bounding boxes **overlaid** where the detector
  produced them.

### The overlay needs a small backend fix

Bounding boxes are stored in the coordinate space of the image the detector
actually ran on — which is *downscaled*, not the original. The ONNX provider
records that space in `metrics.input_width/height`; **the heuristic provider
records no dimensions at all**, so its boxes cannot be placed reliably.

Fix: `cv_client` records `image_width`/`image_height` in `CvResult.metrics`
for **both** providers. Then the client can express each box as a percentage
and overlay it on any rendered size, with no dependency on the downscale rule
staying the same.

Overlay is drawn as absolutely-positioned divs over the `<img>` (percentage
coordinates), not a composited image — nothing to generate, cache, or
invalidate. Where a detection has no bbox (the heuristic provider emits none
for utensils and drains), the finding still appears in the list; the overlay
is additive, never the only way to see it.

### Flagged view (`/reviewer/flagged`)

Open flags, newest first, with the reason, who raised it, and when. A toggle
reveals resolved history. Each row links to the stall and offers **Resolve**
with an optional note.

### Flag action

A modal with a **required** reason field (min 3 chars, max 500) and the
stall's name in the header so a reviewer cannot flag the wrong row. On
success the row's status updates without a full reload.

---

## 7. Chart specifics

Following the visualization method rather than taste:

| Choice | Value | Why |
|---|---|---|
| Form | Line + markers, single series | "Trend over time" → line; markers because observations are discrete |
| Series colour | 1 hue (blue `#2a78d6` light / `#3987e5` dark) | Single series → sequential job, not categorical |
| Legend | **None** | One series — the title names it |
| Grid / axis | `#e1e0d9` hairline, `#c3c2b7` baseline | Recessive chrome |
| Axis labels | `#898781` muted ink | Text wears text tokens, never the series colour |
| Reference line | At 60, "needs work below" | Makes the actionable boundary visible |
| Status colours | Reserved for the band only | Never reused as a series colour |

- **One y-axis.** The chart plots score only. No dual-axis.
- Direct-label the most recent point; not every point.
- **A table of the same history sits below the chart** — required for
  accessibility, and the reviewer wants the exact numbers anyway.
- Colours validated with the skill's `validate_palette.js` before shipping,
  against the actual surface the chart renders on.

The chart is a Client Component so it can carry a hover crosshair + tooltip
(the method's default interaction for line charts). That costs hydration on
one desktop panel, which is irrelevant here.

---

## 8. Tests

| File | Covers |
|---|---|
| `test_reviewer_access.py` | Vendor and consumer are rejected on **every** `/reviewer/*` route; anonymous gets 401; reviewer and admin are allowed |
| `test_reviewer_vendors.py` | Filters (search, band, flagged, has_scan), each sort key in both directions, pagination + total, and staleness of derived columns |
| `test_reviewer_queries.py` | **Query-count assertion** — the table endpoint issues a bounded number of queries regardless of row count |
| `test_reviewer_detail.py` | Score history ordered, scan history ordered, images with detections, 404 for a missing stall |
| `test_flags.py` | Create requires a non-blank reason; length bounds; status lifecycle; resolve records reviewer + time; open-only filtering; the partial index behaves |
| `test_public_profile.py` | *(existing)* — re-run, since the `is_flagged` drop touches `StallRead` |
| `frontend .../chart.test.ts` | The SVG path/scale maths: empty history, one point, all-equal scores (a zero-range axis must not divide by zero), and clamping to 0–100 |

The chart's scale maths is pure and is the one place a division-by-zero or an
off-canvas point would silently produce a blank chart, so it gets a unit test
even though the rest of the chart does not.

---

## 9. Dependencies

**None.** No charting library, no table library, no date library. Everything
is Tailwind + hand-rolled SVG over the existing API client.

---

## 10. Explicitly out of scope

Document verification, officer assignment, report prioritization, bulk
actions, CSV export, notifications/email, real-time updates, the consumer
feedback pipeline, the hygiene map, adaptive monitoring intervals, audit
logging, and the Admin role's own screens.

The existing `GET /vendors/` endpoint stays (it is tested) but the dashboard
no longer calls it — `/reviewer/vendors` supersedes it. I'll note it as
deprecated rather than delete it in this phase.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| N+1 on the table endpoint | Single window-function query + a query-count test |
| Client-side filtering silently hides rows | Filter/sort/paginate server-side |
| Status colour treated as the only signal | Colour + icon + label everywhere; enforced by a component, not by convention |
| Overlay boxes misplaced | Record the detector's coordinate space for both providers; percentage-based rendering |
| Dropping `is_flagged` touches Phase 1–4 code | 3 files, no test references; 394 existing tests as the net |
| Chart maths producing a blank panel | Pure scale function, unit-tested on the degenerate cases |
| Filtering on a derived column ("latest score") | Computed in the same SQL statement, not in Python |

---

## 12. Proposed commit sequence

1. `refactor: drop stalls.is_flagged; add flags table (migration 0005)`
2. `feat: record detector coordinate space in cv_client metrics`
3. `feat: reviewer queries — aggregate vendors table with server-side filter/sort`
4. `feat: reviewer endpoints — vendors, detail, summary, flags`
5. `feat: vendors table, flagged view, flag dialog`
6. `feat: vendor detail — score chart, scan history, image gallery with overlays`
7. `test: reviewer access, filters, query count, flags, chart maths`

---

**Two things worth a steer before I start:**

1. **§2** — confirm dropping `stalls.is_flagged` (it is currently written by
   nothing).
2. **§6** — whether to backport the colour+icon+label treatment to the Phase 3
   mobile history cards, which currently band the score by colour alone.
