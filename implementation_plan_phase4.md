# Implementation Plan — Phase 4: QR Code + Public Consumer Profile

Status: **IMPLEMENTED** — see "Deltas from this plan" immediately below for
where the built system diverges from what was approved.

Builds on: Phases 1–3 (Foundation, Product Scan, Hygiene CV).

---

## Deltas from this plan

### The §2 schema change went ahead

`stalls.qr_code_id` was dropped; `qr_codes` is the single source of truth.
`StallRead.qr_code_id` is preserved as a derived property, so **no API
consumer sees a change**. The blast radius was exactly as measured: 4
backend files, 1 migration, 3 test call sites, 2 frontend spots.

Migration 0004's ordering is the load-bearing part and is commented as such:
create → **backfill** → drop. Reversing the last two would destroy every
existing stall's code irrecoverably.

### Test failures that found real issues

| # | Problem | Resolution |
|---|---|---|
| 1 | `test_survives_a_scuffed_sticker` failed — occluding a corner made the code undecodable | **The test was wrong, and so was my code comment.** Error correction protects *data* modules, not the three finder patterns; losing one is fatal at any EC level. Split into two tests that assert both behaviours, and corrected the misleading comment in `services/qr/service.py` |
| 2 | `stallCodeFromScan` rejected a 32-character alphabet string | Test bug: the parser's bound is 4–16 characters, because a real code is 10. Test rewritten to cover the distinctive letters within a valid length |

Neither was a product bug, but #1 corrected a claim I had written into the
code, which is the more valuable outcome.

### Additions beyond the approved plan

1. **`not-found.tsx` for the public route.** `notFound()` would otherwise
   fall through to the app-wide 404, which is not stall-shaped.
2. **`robots: { index: false }` on the public page metadata.** The page is
   public, but there is no reason to build a searchable registry of named
   businesses out of it.
3. **`generateMetadata`** so a shared link shows the stall name rather than
   the app title.
4. **A manual code-entry field on the consumer screen**, not just a camera.
   On an insecure origin the camera is simply unavailable, and a dead end at
   the front door of the consumer experience is worse than a text input
   nobody usually needs.
5. **Descriptive rejection messages.** `describeScanRejection` names the
   forbidden characters (`I, L, O, U`) when a code is the right shape but
   the wrong alphabet, which is the common case for a mistyped code.
6. **The finder-pattern limitation is documented in the UI rationale**, not
   only in code: the vendor card is plain white with nothing overlapping
   because a covered corner marker is unrecoverable.

### Where the build differs from the plan's structure

- `core/constants.py` holds `DISCLAIMER` and `DISCLAIMER_SHORT`; the hygiene
  endpoint now imports it rather than defining its own copy, so the two
  cannot drift.
- `fetchQrBlob` in `lib/api.ts` exists because the QR image endpoint is
  authenticated — a plain `<img src>` cannot attach the bearer token. Both
  the vendor screen and the download button fetch it explicitly.
- `test_vendor_onboarding.py` is new and not in the plan's test list. Writing
  it revealed that `onboard_vendor` had **no direct coverage through Phases
  2–3** — it was only exercised incidentally. Worth knowing.
- Two Starlette deprecation warnings were cleared while touching those files
  (`HTTP_422_UNPROCESSABLE_ENTITY` → `..._CONTENT`, and the 413 equivalent).

### Verification status

- **394 backend tests pass**, up from 310. **19 frontend tests pass.**
- Frontend: `tsc --noEmit` clean and `next build` succeeds (13 routes).
- QR rendering is verified by **decoding the rendered image with OpenCV**,
  not merely asserting PNG bytes exist — including a damaged-data-module
  case and a contrasting finder-pattern case.
- **Not verified against live services.** Same caveat as Phases 2–3: no
  PostgreSQL was reachable, so migration 0004 and its backfill are validated
  by construction (offline DDL generation, SQLite-backed runs). The backfill
  has never run against real rows, because there are none yet.

---

## 1. Decisions locked (from your answers)

1. **`/stall/<id>` carries the `qr_code_id`, not the serial primary key.** The
   route shape is unchanged; the segment holds the stall's random 10-character
   code. A serial id would let anyone walk `/stall/1`, `/stall/2`, … and scrape
   every stall's hygiene score.
2. **The product-scan summary shows status + date, not the product name.** A
   consumer learns "the last label check came back clear" without the app
   publishing a named brand's verdict from a rules engine.

---

## 2. One deliberate schema change you should push back on if you disagree

Phase 1 put the QR identifier on `stalls.qr_code_id` (NOT NULL UNIQUE) and
Phase 2 built the scanner around it. You have now asked for a `qr_codes`
table, which means the same string would live in two places.

**I propose making `qr_codes` the single source of truth and dropping
`stalls.qr_code_id`.**

Why not keep both:

- The moment code regeneration or revocation exists — the whole reason to
  have a ledger table — the two can disagree. If they disagree, **a printed
  QR sticker stops resolving**, and that is discovered by a customer standing
  at a stall, not by a test.
- Right now nothing updates either value, so the duplication is harmless *in
  practice*. That is precisely why it would survive review and then break
  later.

Why this is the cheap moment: **the database does not exist yet.** No `.env`,
no migrations have ever been applied, and no QR code has been printed.
Doing this after 500 stalls have stickers is a data migration with physical
consequences.

Blast radius, measured rather than guessed:

| Surface | Count |
|---|---|
| Backend files referencing `qr_code_id` | 4 (`models/stall.py`, `crud/stall.py`, `services/qr/service.py`, `services/vendors/service.py`) |
| Other | `schemas/stall.py`, migration `0001`, 3 test call sites |
| Frontend | `lib/types.ts`, `(mobile)/vendor/page.tsx` |

**The external API contract does not change.** `StallRead.qr_code_id` stays in
the response, backed by a property that reads the stall's active code. The
vendor app and any consumer of that endpoint see no difference.

If you would rather not touch Phase 1/2 code, say so and I will keep the
denormalized column with a documented "current code" pointer — but I would be
writing down a hazard rather than removing one.

---

## 3. Folder structure (Phase 4 additions)

```
backend/
├── alembic/versions/
│   └── 0004_phase4_qr.py             # NEW — qr_codes, backfill, drop stalls.qr_code_id
└── app/
    ├── core/
    │   ├── config.py                 # UPDATED — PUBLIC_APP_URL
    │   └── constants.py              # NEW — the shared advisory disclaimer
    ├── models/
    │   ├── enums.py                  # UPDATED — QrCodeStatus
    │   ├── qr_code.py                # NEW — QrCode
    │   └── stall.py                  # UPDATED — drop qr_code_id, add relationship
    ├── schemas/
    │   ├── public.py                 # NEW — the public allow-list, isolated
    │   └── stall.py                  # UPDATED — qr_code_id becomes derived
    ├── crud/qr_code.py               # NEW
    ├── services/
    │   ├── qr/service.py             # UPDATED — issue/revoke/resolve, PNG rendering
    │   └── public/service.py         # NEW — assembles the public profile
    └── api/v1/endpoints/
        ├── public.py                 # NEW — unauthenticated
        └── stalls.py                 # UPDATED — QR image + code endpoints

frontend/src/
├── app/
│   ├── (public)/stall/[id]/page.tsx  # REWRITTEN — was entirely mock data
│   ├── (mobile)/vendor/qr/page.tsx   # NEW — full-screen code + download
│   └── (mobile)/consumer/page.tsx    # REWRITTEN — real QR scanner
├── lib/
│   ├── api.ts                        # UPDATED — public profile + QR image
│   ├── qr.ts                         # NEW — scanned-text -> stall code (pure)
│   └── types.ts                      # UPDATED
└── components/
    ├── mobile/BottomNav.tsx          # UPDATED — "My QR" tab
    └── qr/QrScanner.tsx              # NEW
```

---

## 4. Data model

**`qr_codes`**

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `stall_id` | FK stalls, indexed | |
| `code` | String(16), **unique**, indexed | The value in the URL and the QR |
| `is_active` | Boolean, default true | A revoked code stops resolving |
| `created_at` | timestamptz | |
| `revoked_at` | timestamptz, nullable | |

**One active code per stall**, enforced by a partial unique index
(`UNIQUE (stall_id) WHERE is_active`) — PostgreSQL supports this, and it makes
"revoke old, issue new" safe rather than a race. A plain `UNIQUE(stall_id)`
would forbid ever issuing a second code, which defeats the point of the table.

The code alphabet stays the Crockford-style set already in
`services/qr/service.py` (no `I`, `L`, `O`, `U`) — these get read aloud,
typed from a printed sticker, and appear in URLs.

**Deliberately NOT included:** `scan_count` / `last_scanned_at`. They are
tempting, but tracking them means a **write on a public, unauthenticated read
endpoint** — write amplification driven by anyone with a script, on the route
you least want that. If you want "your QR was viewed N times" as a vendor
feature, it belongs behind a cheap counter or an async write, in a later
phase. The endpoint stays read-only.

`stalls.hygiene_score` continues to be updated by Phase 3 and is what the
public page reads.

---

## 5. The public endpoint — allow-list, not field removal

```
GET /api/v1/public/stalls/{code}
```

Unauthenticated. Returns **only**:

```json
{
  "stall_name": "Ramesh Vada Pav",
  "food_category": "Street Food",
  "hygiene": { "score": 63.5, "band": "fair", "assessed_at": "2026-09-17T…" },
  "last_scan": { "status": "Suitable", "scanned_at": "2026-09-16T…" },
  "advisory_only": true,
  "disclaimer": "AI-assisted assessment, not an official certification. …"
}
```

`hygiene` is `null` if the stall has never been checked; `last_scan` is `null`
if nothing has been scanned. Both are normal states for a new stall, and the
page must say so plainly rather than showing a zero.

**Why a dedicated `schemas/public.py` and not a filtered internal schema:**
if the public response is built from `StallRead` with fields deleted, then
adding a column to `Stall` next phase silently publishes it. An explicit
allow-list means leaking a field requires someone to *add* it here, which is
a decision a reviewer sees.

**Explicitly excluded, with reasons:**

| Excluded | Why |
|---|---|
| Vendor name, phone, email, `user_id` | The spec forbids contact info; it is also the difference between "a stall" and "a named person" |
| Address, latitude, longitude | Not requested. The consumer is standing at the stall, so it adds no value to them — but it does add value to someone scraping a registry |
| `stall_id`, `vendor_id` | Internal identifiers; publishing them restores enumeration by the back door |
| Stall images, document paths, scan images | Spec forbids. These are also unauthenticated static mounts (Phases 2–3), and a public profile is exactly where that would get noticed |
| Product name / matched ingredients | Your locked decision: no public verdict on a named product |

**Other hardening on this route:**

- Lookup is **case-insensitive** (normalised to upper) so a typed code works,
  tested explicitly.
- `Cache-Control: public, max-age=60` — a short shared cache is appropriate
  for public, non-personal data and blunts scraping.
- Unknown or revoked code → **404 with the same body**, so the response does
  not distinguish "never existed" from "revoked".
- Rate limiting is noted as deferred, not silently omitted.

---

## 6. QR generation

`GET /api/v1/stalls/{stall_id}/qr.png` — authenticated, owner vendor or
reviewer, reusing `get_stall_for_reader` so ownership cannot drift between
resources.

- Rendered with `qrcode` + Pillow, already a dependency.
- **The QR encodes a full URL** — `{PUBLIC_APP_URL}/stall/{code}` — not a bare
  code. This matters: a consumer can point their normal camera app at the
  sticker and it opens, with no app install and no in-app scanner. The
  in-app scanner is then a convenience, not a requirement.
- `box_size` tuned for print (~740 px for a 29-module code), with a bounded
  `?size=` override.
- `?download=1` adds `Content-Disposition: attachment` for the vendor's
  download button; without it the image renders inline in `<img>`.
- Generation is **pure and dependency-free**, so it is unit-testable without a
  database.

---

## 7. Frontend

**`/stall/[id]` — rewritten.** Phase 1's version is entirely mock data:
hardcoded `92/100`, invented "Verified Ingredients", a fake vendor line. It is
replaced with a **server component** that fetches the public profile and calls
`notFound()` on a 404.

- Server-rendered because the data is public and unauthenticated — no token to
  attach, no loading flash, and nothing sensitive ever reaches the client.
- Next 16: `params` is a `Promise`, so it is awaited.
- Sections: stall name + category · hygiene score as a colour-banded dial with
  the assessment date · last label check (status + date) · the advisory notice,
  rendered unconditionally and not dismissible.
- **No "excellent standards" editorialising.** Phase 1's mock asserted "This
  stall has consistently maintained high hygiene scores" — with one check on
  record that would be a fabrication. The page states the score and its date
  and lets the consumer judge.

**`/vendor/qr` — "My QR code".** Full-screen white card at maximum size for
photographing or printing, the stall name, the code in large monospace as a
fallback for a damaged sticker, and a download button. Reachable from a new
**My QR** tab in the bottom nav (the currently-disabled Profile tab stays
disabled).

**`/consumer` — real scanner.** Uses `qr-scanner@1.4.2`: it prefers the native
`BarcodeDetector` where available (Chrome/Android — fast, no WASM) and falls
back to a bundled worker elsewhere (iOS Safari, Firefox). `jsqr` would mean
driving video frames by hand with `requestAnimationFrame`; `html5-qrcode`
carries a much larger bundle for a UI we are building anyway.

- Reuses the `CameraCapture` conventions from Phases 2–3, including the
  **HTTPS/secure-context caveat**: `getUserMedia` is unavailable on
  `http://192.168.x.x`, so the screen says so explicitly and offers a
  "type the code" fallback rather than appearing broken.
- `lib/qr.ts` holds one pure function, `stallCodeFromScan(text)`, handling the
  three real inputs: a full URL, a bare code, and something unrelated. This is
  the single piece of client logic that decides **which stall a consumer is
  shown**, so a sloppy regex is a wrong-stall bug — hence the tests in §9.

---

## 8. Shared pieces

- **The disclaimer moves to `app/core/constants.py`.** Phase 3 defined it in
  `api/v1/endpoints/hygiene.py`; the public page needs the identical string.
  Two copies would drift, and this is the one sentence that must not.
- **`PUBLIC_APP_URL` setting** (default `http://localhost:3000`) — the public
  origin the QR encodes. Distinct from `BACKEND_PUBLIC_URL`, which points at
  the API.

---

## 9. Tests

| File | Covers |
|---|---|
| `test_public_profile.py` | **The allow-list test: asserts the response keys are exactly the documented set**, so adding a field to `Stall` cannot leak one. Plus: no assessment yet, no scans yet, revoked code → 404, unknown code → 404, case-insensitive lookup, identical 404 bodies |
| `test_qr_codes.py` | Code alphabet excludes look-alike characters; issue/resolve/revoke; one-active-per-stall; the partial unique index behaviour |
| `test_qr_rendering.py` | PNG bytes are a valid image of the expected size; the encoded payload is the full public URL; bounds on `?size=` |
| `test_stall_onboarding.py` | Onboarding issues a `qr_codes` row in the same transaction; `StallRead.qr_code_id` still populated |
| `frontend/src/lib/qr.test.ts` | `stallCodeFromScan`: full URL, bare code, lowercase, trailing slash/query, and **rejecting** unrelated URLs and text |

**Frontend test infra:** this adds `vitest` (config + one dep) for that single
file. That is a real addition, so the justification is narrow: it is the one
client-side function where a bug routes a consumer to the wrong stall, and it
establishes the runner that the deferred reviewer-dashboard work will need.
Say the word if you would rather I skip it and rely on manual checks.

Backend tests run on SQLite as in Phases 2–3, with PostgreSQL-only details
(the partial unique index) covered by asserting the migration's DDL.

---

## 10. Dependencies

| Package | Where | Verified |
|---|---|---|
| `qr-scanner@^1.4.2` | frontend | Only dep is `@types/offscreencanvas`; native fast path + worker fallback |
| `vitest` + `@vitejs/plugin-react` | frontend (dev) | For `lib/qr.ts` only |
| `qrcode[pil]` | backend | Already installed since Phase 1 |

No backend runtime dependency is added.

---

## 11. Explicitly out of scope

Reviewer dashboard wiring (still mock data — a Phase 5 candidate), consumer
feedback and anti-manipulation, the hygiene map, adaptive monitoring
intervals, document verification, audit logging, the Admin role, QR
regeneration/revocation *endpoints* (the schema supports them; the UI does
not), scan analytics, and rate limiting.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Public endpoint leaks a new field later | Explicit allow-list schema + a test asserting the exact key set |
| A printed QR stops resolving after a schema change | `qr_codes` is the single source of truth; no dual write to drift |
| Scraping despite the random code | 32¹⁰ space, 60s shared cache, uniform 404s; rate limiting documented as deferred |
| Consumer cannot use the scanner over plain HTTP on a phone | Same secure-context constraint as Phases 2–3: stated in the UI, with a manual code-entry fallback |
| Dropping `stalls.qr_code_id` breaks Phase 2/3 | Blast radius enumerated in §2; `StallRead.qr_code_id` preserved; 310 existing tests as the safety net |
| A wrong verdict publicly shown against a brand | Locked decision: status + date only, no product name |

---

## 13. Proposed commit sequence

1. `refactor: qr_codes becomes the source of truth (migration 0004 + backfill)`
2. `feat: public stall profile endpoint with an explicit allow-list`
3. `feat: QR PNG rendering + vendor QR endpoints`
4. `feat: public stall page (replaces Phase 1 mock)`
5. `feat: vendor My QR screen + consumer QR scanner`
6. `test: public allow-list, QR lifecycle, rendering, scan-code parsing`

---

**Awaiting your approval.** The one thing I would most like a decision on is
**§2** — whether to normalise away `stalls.qr_code_id` now, or keep the
denormalized column and accept the drift risk. Everything else follows from
the plan as written.
