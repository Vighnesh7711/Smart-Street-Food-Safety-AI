# Implementation Plan — Phase 2: Product Scan with Translation

Status: **IMPLEMENTED** — see "Deltas from this plan" immediately below for
where the built system diverges from what was approved.

Builds on: Phase 1 (Foundation).

---

## Deltas from this plan

Everything below was discovered during implementation. Recorded here rather
than silently absorbed, because each one changes a decision that was
reviewed.

### Bugs found in Phase 1 code

| # | Problem | Resolution |
|---|---|---|
| 1 | `POST /register` passed `user_in.role` straight through — anyone could self-register as `reviewer` or `admin` | Privileged roles rejected with 400; only vendor/consumer are self-assignable |
| 2 | `email-validator` was never in `requirements.txt` despite `EmailStr` being used — registration raised `ImportError` at runtime | Added to requirements |
| 3 | `opencv-python-headless==4.9.0.80` cannot import against numpy 2.x (`numpy.core.multiarray failed to import`) — the hygiene CV phase would have failed outright | Bumped to `>=4.10` (5.0.0.93); verified against numpy 2.5.3 |
| 4 | `get_current_user` returned **403** for a missing/invalid token, so clients could not tell "re-authenticate" from "forbidden" | Now 401 with `WWW-Authenticate: Bearer` |

### Additions beyond the approved plan

1. **Extra precedence row (3a).** The plan's row 3 gated on the *blended*
   score only. Testing showed a scan could report a confident "Potential
   concern" at OCR confidence 0.05, because a misread token matched a real
   ingredient exactly and carried the match/rule terms. Added a hard gate:
   OCR confidence below `SCAN_MIN_USABLE_CONFIDENCE` forces *Needs review*
   regardless of the blend. Uses a setting that had been defined but never
   consumed.

2. **Sync/async not changed, but `SCAN_MIN_USABLE_CONFIDENCE` and
   `SCAN_*` image thresholds** are all wired to `.env` rather than
   hardcoded, beyond what §11 listed.

3. **Devanagari aliases added to the seed.** The plan seeded English
   synonyms only. Since OCR supports Devanagari and the target user reads
   Hindi/Marathi, `हल्दी`, `नमक`, `चीनी`, `मैदा`, `सरसों तेल`, `दूध पाउडर`
   and others were added to the knowledge base.

4. **Seed self-validation.** `ingredients_seed._validate()` checks for
   duplicate aliases, invalid statuses, and malformed rules before touching
   the database. It caught a real collision: `red 3` was claimed by both
   Carmoisine and Erythrosine, which would have violated the unique
   constraint on `normalized_alias` and failed the entire seed.

### Where the build differs from the plan's structure

- `app/api/routes/` → `app/api/v1/endpoints/` happened as planned.
- `frontend/src/middleware.ts` → **`src/proxy.ts`**. Next.js 16 deprecated
  the `middleware` convention; the file was renamed and the export is now
  `proxy`. The plan did not anticipate this (it predates reading the bundled
  Next 16 docs).
- `services/products/status_engine.py` gained `resolve_ocr_confidence` and
  `compute_confidences` as separate exported functions rather than being
  inlined into `decide_status`, so the precedence table stays independently
  testable.
- Two extra modules not in the plan's tree: `app/db/types.py` (portable
  JSON/JSONB) and `app/schemas/ingredient.py`.

### Verification status

- **143 tests pass** (`pytest`), covering normalization, extraction,
  matching, precedence, confidence, translation fallback, and the full
  pipeline end to end with OCR mocked.
- Frontend: `tsc --noEmit` clean and `next build` succeeds.
- **Not yet verified against live services.** No PostgreSQL was reachable at
  implementation time, and no Google credentials were supplied, so
  migrations, the seed, and real OCR/Translate calls have been validated
  only by construction (offline SQL DDL generation, SQLite-backed pipeline
  runs, mocked providers). First `alembic upgrade head` + seed run is still
  the user's to perform.

---

## 1. What Phase 1 actually left behind

I read the Phase 1 code rather than assuming it matched its spec. Relevant findings:

| Area | State | Impact on Phase 2 |
|---|---|---|
| `alembic/versions/` | **Empty — zero migrations** | No tables exist; Phase 2 needs new tables |
| `POST /api/v1/vendors/onboard` | **Stub** — returns `{"status":"success"}`, writes nothing | Blocking: scan requires a real `stall_id` |
| Login (`login/page.tsx`) | **Fake** — client-side `router.push`, no API call, no token stored | Blocking: scan endpoint needs auth |
| `frontend/src/lib/` | **Does not exist** — no API client, no token storage | Blocking: need a fetch wrapper |
| `app/services/`, `app/integrations/`, `app/workers/` | **Do not exist** (spec'd in Phase 1, never created) | Phase 2 creates them |
| API routes location | `app/api/routes/`, not `app/api/v1/` | Migration to `v1/` proposed (§4) |
| `app/models/product.py` | Exists: `stall_id, name, ingredients_text, status, explanation` | Extended, not replaced |
| `app/models/vendor.py` | `preferred_language` exists ✅ | Scan pipeline reads it — no change needed |
| Reviewer dashboard | Hardcoded mock arrays | Out of Phase 2 scope, untouched |
| Tests | **No pytest, no test dir** | Phase 2 adds the scaffold |
| `backend/.env` | **Does not exist** | ⚠️ Backend cannot boot — see §3 |

**Phase 1 is a UI skeleton with a partial backend.** The scan flow cannot be demoed end-to-end on top of it, which is why §5 includes a small "unblock" sub-phase.

---

## 2. Decisions locked (from your answers)

1. **OCR = Google Cloud Vision** (`document_text_detection`). PaddleOCR was ruled out by evidence: `paddlepaddle` publishes **no wheel for cp314**, so it is not installable on this venv. Vision is already installed and already in `requirements.txt`, reuses the service-account credentials Translate needs, and has the strongest Devanagari accuracy of the candidates.
2. **Close the Phase 1 gaps minimally** (§5) so the scan is runnable end-to-end.
3. **Synchronous scan endpoint** — one `POST` returns the finished result. `workers/` is scaffolded with a documented upgrade path.

### Verified dependency availability (Python 3.14.7 / Windows)

All new deps below were dry-run tested against your actual venv:

| Package | Result |
|---|---|
| `pytest` | ✅ 9.1.1 |
| `pytest-cov` | ✅ 7.1.0 |
| `httpx` | ✅ 0.28.1 (required by FastAPI `TestClient`) |
| `RapidFuzz` | ✅ 3.14.6 — **cp314 wheel exists** |
| `paddlepaddle` | ❌ **no distribution** |
| Tesseract binary | ❌ not installed on this machine |

---

## 3. ⚠️ Pre-flight blocker (you must do this)

`alembic/env.py` imports `app.core.config.settings`, which declares `JWT_SECRET_KEY` and `DATABASE_URL` as **required with no defaults**, and there is **no `backend/.env`**. So `uvicorn`, `alembic`, and every import of `app.main` currently fail at startup.

Before any Phase 2 step runs, you need:

```bash
cd backend
cp .env.example .env
# then fill in DATABASE_URL and JWT_SECRET_KEY (openssl rand -hex 32)
```

I will not create `.env` or invent key values — that's yours by design. `.env` is already gitignored.

---

## 4. Target folder structure

```
Smart_Street_Food_Safety_Ai/
├── implementation_plan.md            # this file
├── backend/
│   ├── .env.example                  # UPDATED — every var documented
│   ├── requirements.txt              # UPDATED
│   ├── pytest.ini                    # NEW
│   ├── alembic/versions/
│   │   ├── 0001_phase1_initial.py    # NEW — users/vendors/stalls/products/food_items
│   │   └── 0002_phase2_scan.py       # NEW — KB tables + product scan columns
│   ├── app/
│   │   ├── main.py                   # UPDATED — mount v1 router aggregate
│   │   ├── api/
│   │   │   ├── dependencies.py       # UPDATED — add require_roles()
│   │   │   └── v1/                   # MOVED from api/routes/ (spec'd in Phase 1)
│   │   │       ├── router.py         # NEW — aggregates all v1 routers
│   │   │       └── endpoints/
│   │   │           ├── auth.py       # MOVED (unchanged logic)
│   │   │           ├── vendors.py    # MOVED + real onboard
│   │   │           ├── stalls.py     # NEW — stall detail / my stalls
│   │   │           ├── products.py   # NEW — scan + history
│   │   │           └── ingredients.py# NEW — knowledge-base read (debug/reviewer)
│   │   ├── core/
│   │   │   ├── config.py             # UPDATED — add scan/threshold/OCR settings
│   │   │   └── security.py           # unchanged
│   │   ├── db/                       # unchanged
│   │   ├── models/
│   │   │   ├── enums.py              # NEW — ScanStatus + shared enums
│   │   │   ├── ingredient.py         # NEW — Ingredient, IngredientSynonym
│   │   │   ├── ingredient_rule.py    # NEW — IngredientRule, Recommendation
│   │   │   ├── product_ingredient.py # NEW — join table w/ match evidence
│   │   │   └── product.py            # UPDATED — scan result columns
│   │   ├── schemas/
│   │   │   ├── product.py            # NEW
│   │   │   ├── stall.py              # NEW
│   │   │   ├── vendor.py             # NEW
│   │   │   └── ingredient.py         # NEW
│   │   ├── crud/
│   │   │   ├── product.py            # NEW
│   │   │   ├── stall.py              # NEW
│   │   │   └── ingredient.py         # NEW
│   │   ├── services/
│   │   │   ├── vendors/service.py    # NEW — onboard vendor+stall transaction
│   │   │   ├── qr/service.py         # NEW — qr_code_id generation (image endpoint deferred)
│   │   │   └── products/
│   │   │       ├── scan_service.py        # NEW — pipeline orchestrator
│   │   │       ├── image_quality.py       # NEW — OpenCV quality gate
│   │   │       ├── ingredient_extraction.py # NEW — locate ingredient section
│   │   │       ├── normalization.py       # NEW — text → normalized tokens
│   │   │       ├── matching.py            # NEW — token → KB ingredient
│   │   │       ├── status_engine.py       # NEW — rules → 5 statuses + confidence
│   │   │       └── explanation.py         # NEW — template render + translate
│   │   ├── integrations/
│   │   │   ├── ocr_client.py         # NEW — Google Cloud Vision wrapper
│   │   │   └── translate_client.py   # NEW — Cloud Translate + fallback + cache
│   │   ├── workers/
│   │   │   └── README.md             # NEW — documents the sync→async upgrade path
│   │   └── seeds/
│   │       ├── __init__.py
│   │       └── ingredients_seed.py   # NEW — 25 ingredients + synonyms + rules
│   └── tests/
│       ├── conftest.py
│       ├── test_normalization.py
│       ├── test_matching.py
│       ├── test_ingredient_extraction.py
│       ├── test_status_engine.py
│       ├── test_translate_fallback.py
│       └── test_scan_endpoint.py     # OCR mocked at the integrations boundary
└── frontend/
    └── src/
        ├── lib/
        │   ├── api.ts                # NEW — typed fetch wrapper w/ JWT
        │   ├── auth.ts               # NEW — token storage/refresh
        │   └── types.ts              # NEW — shared API types
        ├── components/
        │   ├── vendor/CameraCapture.tsx   # NEW — full-screen camera + guide overlay
        │   └── scan/ScanResultCard.tsx    # NEW — status badge, translate toggle
        └── app/(mobile)/
            ├── layout.tsx            # UPDATED — working bottom nav
            └── vendor/
                ├── page.tsx          # UPDATED — real stall create
                └── scan/page.tsx     # NEW — scan flow
```

**Why `services/products/` is a package, not a file:** hygiene (§ scope item 2) becomes `services/hygiene/` with the same internal shape (`coverage.py`, `cv_indicators.py`, `scoring.py`). Nothing restructures when it lands.

---

## 5. Work breakdown

### Phase 2a — Unblock (small, mechanical)

| # | Step | Files |
|---|---|---|
| a1 | Move `api/routes/` → `api/v1/endpoints/`, add aggregating `router.py`, update `main.py` | 5 files |
| a2 | Add `require_roles(*roles)` dependency factory; replace ad-hoc inline role checks | `dependencies.py`, `vendors.py` |
| a3 | Write `0001_phase1_initial` migration covering the 5 existing tables | 1 migration |
| a4 | Real `POST /vendors/onboard`: creates `Vendor` + `Stall` (+ `qr_code_id`) in one transaction, idempotent | service + endpoint + schema |
| a5 | Frontend `lib/api.ts` + `lib/auth.ts`; real login storing JWT in a cookie (so `middleware.ts` works) | 2 new + `login/page.tsx` |
| a6 | Wire `(mobile)/layout.tsx` bottom nav to real routes; vendor page posts to onboard | 2 files |
| a7 | pytest scaffold: `pytest.ini`, `tests/conftest.py`, fixtures | 2 files |

**Security fix included in a5:** `POST /register` currently lets anyone self-assign `role="reviewer"` or `"admin"` (`crud/user.py:18` passes `user_in.role` straight through). Phase 2a restricts public registration to `vendor`/`consumer` and rejects privileged roles with 400.

### Phase 2b — Knowledge base

| # | Step |
|---|---|
| b1 | `models/enums.py`: `ScanStatus` (5 values), `IngredientCategory`, `RiskLevel`, `RuleType` |
| b2 | 4 models + `product_ingredients` join table (§6) |
| b3 | `0002_phase2_scan` migration + `products` column additions |
| b4 | `seeds/ingredients_seed.py` — 25 ingredients (§7); idempotent upsert keyed on canonical name |
| b5 | CLI entrypoint: `python -m app.seeds.ingredients_seed` |

### Phase 2c — Integrations

| # | Step |
|---|---|
| c1 | `integrations/ocr_client.py` — returns `OcrResult{text, mean_confidence, word_count, engine}` |
| c2 | `integrations/translate_client.py` — `translate_text(text, target)` → `TranslationResult{text, translated: bool, warning, provider}` |

Both are thin, provider-shaped wrappers behind a stable interface, so swapping OCR/translate providers later touches one file each.

### Phase 2d — Pipeline

`scan_service.scan_label(...)` orchestration (§8), then `POST /products/scan`.

### Phase 2e — Mobile UI

Camera capture → loading → result card (§9).

### Phase 2f — Tests

Unit tests as listed in §10.

---

## 6. Data model

### Existing tables (extended)

**`products`** — add:

| Column | Type | Purpose |
|---|---|---|
| `scan_image_path` | String | stored upload, for reviewer audit + retake UX |
| `ocr_raw_text` | Text | full OCR output |
| `ocr_confidence` | Float | stage confidence |
| `match_confidence` | Float | stage confidence |
| `rule_strength` | Float | stage confidence |
| `confidence_score` | Float | weighted overall |
| `explanation` | Text | **exists** — English canonical |
| `explanation_translated` | Text | NEW — vendor-language text |
| `language_code` | String(8) | NEW — target used |
| `translation_failed` | Boolean | NEW — the graceful-fallback warning flag |
| `image_quality` | JSONB | metrics + issues list |
| `retake_required` | Boolean | NEW — drives "Needs review" UI prompt |
| `scanned_by_user_id` | FK users | NEW — who scanned |

`status` stays a `String` validated by the `ScanStatus` enum rather than becoming a PG enum type — avoids a destructive type migration on a populated column, and keeps adding a 6th status a code-only change.

### New tables

**`ingredients`**
`id`, `canonical_name` (unique, indexed), `category`, `default_risk_level`, `description`, `is_active`, `created_at`

**`ingredient_synonyms`** *(5th table — justified below)*
`id`, `ingredient_id` FK, `alias`, `normalized_alias` (unique index), `alias_type` (`common_name` / `e_number` / `ins_number` / `ocr_variant`)

> **Why a table and not a JSON column:** matching is the hot path — one lookup per token per scan. A unique index on `normalized_alias` makes stage-1 matching a single indexed query, and E-numbers/INS numbers (`211`, `E211`, `INS 211`) are naturally rows, not nested JSON. Seeding and extending the synonym set stays data-only.

**`ingredient_rules`**
`id`, `ingredient_id` FK, `rule_type`, `conditions` (JSONB), `severity`, `status_on_match` (one of the 5 statuses), `explanation_template` (English, named placeholders), `is_active`

`rule_type` ∈ `presence` | `threshold` | `category_restriction`
- `presence` — any amount triggers
- `threshold` — `{"max_pct": 2.0}`, compares against the parsed `%` in the label
- `category_restriction` — `{"allowed_categories": [...]}`, compared against `stalls.food_category` → drives **Application mismatch**

**`recommendations`**
`id`, `rule_id` FK (nullable), `ingredient_id` FK (nullable), `title`, `body` (English), `priority`, `is_active`

**`product_ingredients`**
`id`, `product_id` FK, `ingredient_id` FK, `matched_text` (raw OCR substring), `matched_alias`, `match_confidence`, `match_method` (`exact`/`alias`/`fuzzy`/`e_number`), `position_in_text`

Unique on `(product_id, ingredient_id)`.

---

## 7. Seed knowledge base — 25 ingredients

Each gets synonyms, a category, a risk level, **one** rule, **one** English explanation template, and 1–2 recommendations.

| # | Ingredient | Category | Risk | Rule → status |
|---|---|---|---|---|
| 1 | Palm Oil | Fat/Oil | High | threshold → Potential concern |
| 2 | Palmolein Oil | Fat/Oil | High | threshold → Potential concern |
| 3 | Hydrogenated Vegetable Oil (Vanaspati) | Fat/Oil | High | presence → Potential concern |
| 4 | Monosodium Glutamate (MSG / Ajinomoto) | Flavour enhancer | Moderate | presence → Potential concern |
| 5 | Sodium Benzoate (INS 211) | Preservative | Moderate | category_restriction → Application mismatch |
| 6 | Potassium Sorbate (INS 202) | Preservative | Moderate | threshold → Potential concern |
| 7 | Sodium Nitrite (INS 250) | Preservative | High | category_restriction → Application mismatch |
| 8 | Calcium Propionate (INS 282) | Preservative | Low | threshold → Potential concern |
| 9 | Tartrazine (INS 102) | Artificial colour | High | category_restriction → Application mismatch |
| 10 | Sunset Yellow (INS 110) | Artificial colour | High | category_restriction → Application mismatch |
| 11 | Carmoisine (INS 122) | Artificial colour | High | presence → Potential concern |
| 12 | Allura Red (INS 129) | Artificial colour | High | presence → Potential concern |
| 13 | Brilliant Blue (INS 133) | Artificial colour | Moderate | presence → Potential concern |
| 14 | Erythrosine (INS 127) | Artificial colour | High | presence → Potential concern |
| 15 | Caramel Colour (INS 150) | Colour | Low | presence → Potential concern |
| 16 | Aspartame (INS 951) | Sweetener | Moderate | presence → Potential concern |
| 17 | Saccharin (INS 954) | Sweetener | Moderate | presence → Potential concern |
| 18 | Sucralose (INS 955) | Sweetener | Low | presence → Potential concern |
| 19 | High Fructose Corn Syrup | Sweetener | Moderate | presence → Potential concern |
| 20 | Refined Sugar | Sweetener | Low | threshold → Potential concern |
| 21 | Iodised Salt | Mineral | Low | threshold → Potential concern |
| 22 | Refined Wheat Flour (Maida) | Cereal | Low | presence → Potential concern |
| 23 | TBHQ (INS 319) | Antioxidant | Moderate | presence → Potential concern |
| 24 | Soy Lecithin (INS 322) | Emulsifier | Low | presence → Potential concern |
| 25 | Citric Acid (INS 330) | Acidity regulator | Low | presence → Potential concern |

Healthier variants without any rule (→ **Suitable**): *Turmeric, Edible Vegetable Oil, Milk Solids, Whey Powder*. These matter — without rule-free ingredients the pipeline can never emit "Suitable" and the status is untestable.

Each `explanation_template` is a **single English string with named placeholders**, e.g.:

```
"{ingredient} is a synthetic food colour. It is permitted under FSSAI rules
only in specified food categories; this product is sold as {category}, which
is outside the permitted list."
```

Canonical English is always generated first, then translated. This keeps one source of truth for the reviewer dashboard and makes the "show original English" toggle trivially correct.

---

## 8. Scan pipeline

```
image bytes
  │
  ├─ 1. image_quality.assess()        OpenCV, no network
  │       ├─ Laplacian variance      → blur
  │       ├─ mean luminance + clip % → too dark / blown out
  │       ├─ specular highlight %    → glare on laminated label
  │       └─ min resolution          → too small to OCR
  │     FAIL → Needs review (retake), pipeline stops. No OCR spend.
  │
  ├─ 2. ocr_client.run()             Google Cloud Vision
  │
  ├─ 3. ingredient_extraction        anchor on "Ingredients" / "सामग्री" / "घटक"
  │     missing → Insufficient information
  │
  ├─ 4. normalization                lowercase, NFC, strip punctuation/%,
  │                                  split on , ; • / newline, canonicalise
  │                                  "INS 211"/"E211" → "e211"
  │
  ├─ 5. matching                     alias index → substring → RapidFuzz ≥88
  │                                  each match keeps its confidence + evidence
  │
  ├─ 6. status_engine                rules fire → status + confidence
  │
  ├─ 7. explanation                  render English template + recommendations
  │
  └─ 8. translate_client             EN → vendor.preferred_language, with fallback
```

### Confidence

```
match_conf = 0.7 * mean(match quality) + 0.3 * coverage
             coverage = matched_ingredient_count / parsed_token_count

overall = 0.40*ocr_confidence + 0.40*match_conf + 0.20*rule_strength

rule_strength = max severity triggered → {low: 0.5, moderate: 0.7, high: 0.9}
                no rule triggered      → 0.6
```

All weights and thresholds live as named constants in `status_engine.py` so they are tunable without hunting through logic.

### Status precedence — evaluated top-down, first match wins

| # | Condition | Status | Retake? |
|---|---|---|---|
| 1 | Image quality gate fails | **Needs review** | ✅ |
| 2 | No ingredient section, or < 2 tokens parsed, or 0 KB matches | **Insufficient information** | ❌ (message names what was missing) |
| 3 | `overall < REVIEW_THRESHOLD` (0.45) | **Needs review** | ✅ |
| 4 | Any triggered rule → Application mismatch | **Application mismatch** | ❌ |
| 5 | Any triggered rule → Potential concern | **Potential concern** | ❌ |
| 6 | Otherwise | **Suitable** | ❌ |

Distinction that matters for UX: **Insufficient information** means *"we read the label, the ingredient list isn't there or isn't legible enough to use"* (no point retaking the same shot). **Needs review** means *"we're not confident in what we read"* (retake helps). Only Needs review shows the retake prompt.

### Honest note on OCR confidence

Google Vision's `document_text_detection` **does not reliably populate per-word `confidence`** (the field is frequently unset). `ocr_client.py` will therefore use per-word confidence *when present* and otherwise fall back to a deterministic signal: `0.6*sharpness_score + 0.4*structure_score` (presence of an ingredient anchor, proportion of tokens resolving to the KB). I'll confirm the actual API behaviour against a live call at implementation time and document what was observed in a comment, rather than leaving a silent guess.

---

## 9. Mobile UI — vendor scan

**`/(mobile)/vendor/scan/page.tsx`**

- Full-screen `<video>` via `getUserMedia({ video: { facingMode: 'environment' } })`
- **Label-alignment guide overlay**: dimmed surround, inset rounded-rect cutout, corner brackets, hint text ("Fit the ingredient list inside the frame")
- Shutter button in the thumb zone; large tap targets; safe-area padding
- Capture → canvas → JPEG blob (capped at ~1600px long edge before upload)
- States: `idle → requesting → live → capturing → analyzing → result | error`
- **Fallbacks that will actually happen:** permission denied, no camera, insecure context. `getUserMedia` requires HTTPS on mobile — a LAN-IP dev server is not a secure context, so I add a `<input type="file" accept="image/*" capture="environment">` fallback path and document the HTTPS requirement in the README.

**`ScanResultCard`**

- Color-coded status badge (5 statuses, accessible contrast in light + dark)
- Translated explanation as primary text; matched-ingredient chips with confidence
- Confidence meter, visually de-emphasised when the verdict is confident
- **"Show original English"** toggle — swaps `explanation` ↔ `explanation_translated`
- **Needs review** → prominent retake CTA
- **Insufficient information** → states which view/section was missing, no retake CTA
- Translation fallback → subtle banner ("Translation unavailable — showing English"), driven by `translation_failed`

---

## 10. Tests

| File | Covers |
|---|---|
| `test_normalization.py` | case, Unicode NFC, punctuation, `%` parsing, `INS 211`→`e211`, Devanagari, empty/whitespace |
| `test_matching.py` | exact alias, E-number, multiword substring, fuzzy OCR typo, negative (no false positive on "sodium" alone) |
| `test_ingredient_extraction.py` | anchor found, missing anchor, terminator boundaries, Hindi/Marathi anchors, multi-line |
| `test_status_engine.py` | all 5 statuses + precedence order + confidence weighting math |
| `test_translate_fallback.py` | **mock the Google client to raise** → asserts English passthrough + `translated=False` + warning set; `target="en"` passthrough makes no API call; cache hit path |
| `test_scan_endpoint.py` | `POST /products/scan` with `ocr_client` mocked at the integration boundary; asserts 200 result shape, RBAC rejection, and Needs-review path on a blurred fixture |

`rapidfuzz`, `pytest`, `pytest-cov`, `httpx` append to `requirements.txt`.

---

## 11. Environment variables

`.env.example` gets every variable with a comment on where to obtain it.

| Variable | Required | Consumed by |
|---|---|---|
| `DATABASE_URL` | ✅ | `core/config.py` → `db/session.py`, `alembic/env.py` |
| `JWT_SECRET_KEY` | ✅ | `core/security.py` |
| `GOOGLE_APPLICATION_CREDENTIALS` | ✅ for OCR + Translate | `integrations/ocr_client.py`, `integrations/translate_client.py` |
| `GOOGLE_TRANSLATE_API_KEY` | optional alternative to the above | `integrations/translate_client.py` |
| `GOOGLE_CLOUD_PROJECT` | ✅ with service-account auth | `integrations/translate_client.py` |
| `OCR_PROVIDER` | default `google_vision` | `integrations/ocr_client.py` — swap point |
| `SCAN_UPLOAD_DIR` | default `./var/uploads/scans` | `services/products/scan_service.py` |
| `SCAN_MAX_UPLOAD_MB` | default `8` | `services/products/scan_service.py` |
| `SCAN_OCR_MIN_CONFIDENCE` | default `0.45` | `status_engine.py` |
| `SCAN_TRANSLATION_ENABLED` | default `true` | `translate_client.py` — kill switch |

`Settings` gains the Phase 2 fields with safe defaults, so `pydantic-settings` still boots with only the three Phase 1 vars present.

---

## 12. Explicitly out of scope

Not touched this phase: QR image generation endpoint + public consumer stall page, hygiene CV (scope item 2), reviewer dashboard wiring, consumer mobile home, document verification/DigiLocker, feedback pipeline, hygiene map, adaptive intervals, audit logging, Admin role.

Stall onboarding **does** generate `qr_code_id` (the column is `NOT NULL UNIQUE`), so the QR/public-profile phase is additive.

---

## 13. Risks

| Risk | Mitigation |
|---|---|
| **No `.env`** → nothing boots (§3) | Pre-flight step; I'll verify `uvicorn` imports before starting |
| Google Cloud billing/credentials not enabled | `OCR_PROVIDER` swap point; OCR failure returns a clear 503, not a 500 |
| Vision confidence unreliable | Heuristic fallback designed in, verified against a live call |
| Existing DB may already have Phase 1 tables | Two-migration split: `alembic stamp 0001` then `upgrade head` if tables pre-exist |
| Next.js 16.3.5 breaking changes | Per `frontend/AGENTS.md`, I'll read `node_modules/next/dist/docs/01-app` before writing any frontend code rather than relying on recalled Next.js conventions |
| Camera UX is untestable in CI | Manual test checklist in the README; the file-input fallback is the automated path |

---

## 14. Proposed commit sequence

1. `chore: unblock — migrations, real onboard, real login, test scaffold` (2a)
2. `feat: ingredient knowledge base — models, migration, 25-ingredient seed` (2b)
3. `feat: OCR + Translate integration clients` (2c)
4. `feat: product scan pipeline — 5 statuses, confidence, translation` (2d)
5. `feat: mobile camera scan UI + result card` (2e)
6. `test: normalization, matching, status engine, translate fallback` (2f)

---

**Awaiting your approval.** Once you confirm, I'll start with 2a and you'll need `backend/.env` in place (§3) before the migration steps run.
