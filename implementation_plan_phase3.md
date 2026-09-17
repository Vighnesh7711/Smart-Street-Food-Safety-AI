# Implementation Plan — Phase 3: Computer-Vision Hygiene Monitoring

Status: **IMPLEMENTED** — see "Deltas from this plan" immediately below for
where the built system diverges from what was approved.

Builds on: Phases 1–2 (Foundation, Product Scan).

---

## Deltas from this plan

### Bugs found while building (all caught by tests, not by review)

| # | Problem | Resolution |
|---|---|---|
| 1 | The standing-water signal fired on **every clean surface**. A smooth, low-saturation, mid-bright region satisfied the mask, so `uniform_region_ratio` was 1.0 on a pristine table — the single worst way a hygiene score can fail | Require the region to be *bounded* (2–45% of frame) and to contain *specular glints*. A puddle is bounded and reflective; a dry table is neither |
| 2 | The glint check was **circular**: bright pixels are excluded from the water mask by the mid-brightness condition, so looking for them inside the mask could never succeed | Sample glints from a **dilated** component |
| 3 | The dilation kernel (15 px) was smaller than the hole the smoothness blur punches around each glint (~11 px radius), so glints stayed outside the sampled region and water was never detected | Kernel widened to 31 px — it must exceed the blur radius. Documented at the call site |
| 4 | `open_drain` was gated on `dark_ratio >= 0.30`, meaning it only fired on a near-black photo. A drain is a *localised* dark line, not a dark frame | Dropped the ratio gate; two long, dark, uniform lines is the signal |
| 5 | Drain detection ran Hough on a dark *mask*, which is blind by construction — a dark drain on a dark floor produces a mask with no internal edges | Run Hough on the original image's edges, then filter lines by sampling brightness along each |
| 6 | `lines[:, 0]` crashes on some OpenCV return shapes | Normalise with `np.asarray(lines).reshape(-1, 4)` |
| 7 | `len(elongated)` on an int counter | Fixed; caught on first run |

The first four were only found by testing the heuristic against synthetic
**clean** images. They are recorded here because each one is a false-positive
generator, and a hygiene score that flags tidy stalls teaches vendors to
ignore it entirely.

### Additions beyond the approved plan

1. **`hygiene_scores` records a `formula_version`.** Not in the plan's column
   list, but the deferred "history/feedback weighting" phase needs to tell
   "the stall got worse" apart from "we changed how we score".

2. **`get_provider` / `build_indicator_label_map` are public.** The plan
   described the swap boundary; these make it explicit that new model class
   names arrive via the seeded `cv_labels` rather than a code edit.

3. **The API returns `disclaimer` and `advisory_only` in every check
   payload.** The plan only required the note in the UI. Shipping it in the
   response means a client cannot present a score as a certification by
   simply not rendering the copy.

4. **Score-band helper (`score_band`).** Four bands (good/fair/poor/bad),
   used by both the history list and the results dial so they cannot drift.

5. **`create_check` is idempotent for unfinished checks.** Reopening the app
   mid-flow resumes the same draft rather than littering history with empty
   ones. Not in the plan; a direct consequence of building the capture flow.

### Where the build differs from the plan's structure

- `services/hygiene/` gained `duplicate.py` (planned) but also split
  `checklist.py` out of `scoring.py`, and `coverage.py` exports
  `describe_missing` separately so callers can compose their own phrasing.
- The plan's `hygiene_indicators` table gained `cv_labels`, which turned out
  to be the mechanism that keeps a model swap out of the code.
- `services/hygiene/hygiene_service.py` imports `image_quality` from
  `services/products/`. Deliberate reuse — blur, exposure, and glare are the
  same problem for a stall photo as for a label photo. Noted at the import;
  promote to a shared `services/imaging/` if a third consumer appears.

### Verification status

- **310 tests pass** (`pytest`), up from 143 at the end of Phase 2.
- Frontend: `tsc --noEmit` clean and `next build` succeeds (12 routes).
- The ONNX tests validate letterbox, head decoding, NMS, and coordinate
  mapping against **synthetic tensors**, so they need no downloaded model and
  CI stays hermetic.
- **Not verified against live services.** Same caveat as Phase 2: no
  PostgreSQL was reachable, so migration 0003 and the hygiene seed have been
  validated by construction (offline DDL generation, SQLite-backed runs).
  **No real ONNX model has ever been run through this code** — the letterbox
  and NMS paths are tested against synthetic outputs, not against a real
  YOLOv8 export. That is the first thing to check after exporting one.

---

## 1. Decisions locked (from your answers)

1. **Detector = ONNX Runtime + YOLO-family weights.** Verified: `onnxruntime` 1.30.0 has a cp314 wheel, and `cv2.dnn.readNetFromONNX` is available in your existing headless OpenCV 5.0. This avoids the alternative's real costs — see §2.
2. **Score = 70% visual + 30% checklist.** A vendor cannot tick their way out of visible waste.
3. **Coverage validation = manual vendor tagging** (you delegated this), **plus perceptual-hash duplicate detection** as an integrity guard — see §6.

---

## 2. Why not `ultralytics` + torch

`pip install ultralytics` resolves to this on your venv:

```
torch-2.14.0  torchvision-0.29.0  opencv-python-5.0.0.93
matplotlib  polars  polars-runtime-32  sympy  networkx
nvidia-ml-py  ultralytics-thop  fonttools  kiwisolver  ...
```

Two concrete problems beyond the ~2.5 GB:

- **`opencv-python` vs `opencv-python-headless`.** ultralytics depends on the *non-headless* build, which would sit alongside the headless one you already have. Both install a `cv2` package; whichever was installed last wins, and mixing them is a well-known source of import failures and Qt/display errors. This would be a self-inflicted version of the Phase 1 numpy/OpenCV bug.
- **Nothing in Phase 3 needs autograd, GPU support, or training.** Inference on a fixed graph is all that's required, and ONNX Runtime is typically *faster* than torch on CPU for exactly this workload.

Fine-tuning later still happens in torch — in a **separate** environment — and the result is exported to ONNX and dropped in. The app never needs torch installed.

### Model weights: I will not auto-download a binary

The app will **not** fetch an `.onnx` file from a third-party URL. Silently downloading an unverified binary into a service that reports on people's livelihoods is a supply-chain risk I don't think is worth taking for convenience.

Instead:

- `scripts/export_yolov8_onnx.py` — a documented, self-contained export you run once in a throwaway env (`pip install ultralytics`), producing `yolov8n.onnx` (~12 MB).
- You place it at `CV_MODEL_PATH`. If missing, `cv_client` raises a clear `CvModelUnavailable` with the exact command to run — it does not fail confusingly at inference time.
- **The heuristic provider needs no model file at all**, so the feature works end-to-end on a fresh clone before any export happens.

---

## 3. Honest framing of the placeholder detector

You noted there is no custom-trained hygiene dataset yet. The consequence is worth stating plainly in the plan, not just in a code comment:

**YOLOv8n pretrained on COCO detects 80 everyday object classes. None of them are hygiene indicators.** The mapping below is a *stand-in* that gives the pipeline real detections with real confidences to score, so the plumbing, thresholds, scoring, and UI can all be built and tested now. It is **not** a hygiene model and its precision on real stalls is unknown and probably poor.

| COCO class detected | Mapped stand-in indicator | Plausible? |
|---|---|---|
| `bottle`, `cup`, `wine glass`, `can` | `visible_waste` | Yes, in the waste area |
| `bowl`, `sandwich`, `pizza`, `donut`, `cake`, `banana` | `uncovered_food` | Weak — a bowl ≠ uncovered food |
| `dining table`, `chair`, `bench` | `cluttered_surface` | Very weak |
| high edge density, no detected object | `cluttered_surface` (heuristic) | Better than the above |

Everything COCO-derived lives in one `_COCO_TO_INDICATOR` table. Replacing it with a real fine-tuned model means swapping **one file** (`cv_client.py`), as you asked. The default `CV_PROVIDER=heuristic` is the more defensible of the two for real use today; `onnx_yolo` is opt-in.

---

## 4. Folder structure (Phase 3 additions)

```
backend/
├── scripts/
│   └── export_yolov8_onnx.py         # NEW — run once, in a separate env
├── alembic/versions/
│   └── 0003_phase3_hygiene.py        # NEW
└── app/
    ├── models/
    │   ├── enums.py                  # UPDATED — ViewCategory, CheckStatus, IndicatorCode
    │   ├── hygiene_check.py          # NEW — HygieneCheck
    │   ├── stall_image.py            # NEW — StallImage
    │   ├── hygiene_indicator.py      # NEW — HygieneIndicator (catalog)
    │   └── hygiene_score.py          # NEW — HygieneScore
    ├── schemas/hygiene.py            # NEW
    ├── crud/hygiene.py               # NEW
    ├── services/hygiene/
    │   ├── coverage.py               # NEW — required views, missing-view messaging
    │   ├── duplicate.py              # NEW — aHash/dHash + Hamming
    │   ├── indicators.py             # NEW — detections -> indicator findings
    │   ├── scoring.py                # NEW — the 70/30 formula
    │   ├── checklist.py              # NEW — checklist catalog + scoring
    │   └── hygiene_service.py        # NEW — orchestrator
    ├── integrations/
    │   └── cv_client.py              # NEW — provider interface + both providers
    └── api/v1/endpoints/hygiene.py   # NEW
frontend/src/
├── app/(mobile)/vendor/hygiene/
│   ├── page.tsx                      # NEW — history list
│   ├── new/page.tsx                  # NEW — guided 4-step capture
│   └── [checkId]/page.tsx            # NEW — results
├── components/hygiene/
│   ├── ViewCaptureStep.tsx           # NEW
│   ├── HygieneResultCard.tsx         # NEW
│   └── ChecklistForm.tsx             # NEW
└── lib/types.ts                      # UPDATED
```

`services/hygiene/` mirrors `services/products/` deliberately — same shape, same conventions.

---

## 5. Data model

Four tables, as specced.

**`hygiene_indicators`** — the catalog (seeded, not per-check data)
`id`, `code` (unique), `display_name`, `description`, `default_severity`, **`view_penalties` (JSONB)**, `cv_labels` (JSONB), `is_active`

> **`view_penalties` is the important column.** Waste in the *waste area* is a working bin; waste in the *prep area* is a hazard. Scoring an indicator the same in every view would penalise a stall for owning a bin. It maps view → penalty points, and a view absent from the map means "does not apply":
> ```json
> { "prep_area": 18, "storage_area": 12, "overall": 8, "waste_area": 0 }
> ```

**`hygiene_checks`** — one submission (up to 4 images)
`id`, `stall_id`, `submitted_by_user_id`, `status` (`draft`/`awaiting_views`/`scored`), `missing_views` (JSONB), `coverage_ok`, `indicators_found` (JSONB, GIN-indexed for reviewer filtering), `checklist` (JSONB), `created_at`, `scored_at`

**`stall_images`** — one row per photo
`id`, `hygiene_check_id`, `stall_id`, `view_category`, `image_path`, `quality` (JSONB), `detections` (JSONB), `phash`, `duplicate_of_id`, `created_at`

> Detections are JSONB here rather than a fifth table. They are written once with their image and only ever read back alongside it. `hygiene_checks.indicators_found` carries the queryable summary with a GIN index, which is what the reviewer dashboard will filter on. If Phase 4 needs per-detection analytics, promoting this to `hygiene_detections` is a mechanical migration — say the word and I'll do it now instead.

**`hygiene_scores`** — versioned score computation
`id`, `hygiene_check_id`, `visual_score`, `checklist_score`, `final_score`, `breakdown` (JSONB), `weights` (JSONB), `formula_version`, `computed_at`

> Separate from `hygiene_checks` so a formula change can be recomputed and *compared* rather than overwriting. This is the table that makes your "full history/feedback weighting comes later" phase additive instead of a rewrite.

`stalls.hygiene_score` (already exists) is updated with the latest `final_score`.

---

## 6. Coverage validation

**Required views:** `overall`, `prep_area`, `storage_area`, `waste_area`.

**Manual tagging, not a classifier.** A view classifier needs a labelled dataset of stall photos that does not exist, and would be a second placeholder model stacked on the first. Tagging is one tap on a screen the vendor is already on. Tradeoff, stated plainly: a vendor can mis-tag, and nothing verifies the tag is truthful.

**Integrity guard — perceptual hashing.** Mis-tagging is cheap, so the obvious abuse is uploading the same photo four times. Each upload gets a 64-bit difference hash computed in ~15 lines of numpy/OpenCV (`cv2.img_hash` is contrib-only and not available). Hamming distance ≤ `CV_DUPLICATE_HAMMING_THRESHOLD` (default 5) against an existing image in the same check → the upload is rejected with *"This looks like the same photo you already submitted for the overall view"*. This costs nothing, catches the laziest abuse, and does not pretend to be tamper-proof.

Indicator detection runs **only** when all four views are present. Until then the check stays `awaiting_views` and the API returns:

```json
{ "coverage_ok": false,
  "missing_views": ["storage_area", "waste_area"],
  "message": "Still needed: the storage area and the waste area." }
```

The message names the specific missing views, in vendor-facing language, as specced.

---

## 7. Score formula

```
visual_score    = clamp(100 - Σ penalties, 0, 100)
    penalty_i   = indicator.view_penalties[view]  ×  severity_multiplier
                                                    × detection_confidence
checklist_score = 100 × (items_checked / items_total)
final_score     = 0.70 × visual_score + 0.30 × checklist_score
```

`severity_multiplier`: low 0.6, moderate 0.8, high 1.0.

**Seeded indicators** (7) and their stand-in CV labels:

| Code | Display name | Severity | prep | storage | overall | waste |
|---|---|---|---|---|---|---|
| `visible_waste` | Visible waste or litter | high | 18 | 12 | 8 | **0** |
| `uncovered_food` | Uncovered food | high | 20 | 15 | 10 | 0 |
| `cluttered_surface` | Cluttered work surface | moderate | 10 | 8 | 6 | 0 |
| `dirty_utensils` | Dirty or stored-wet utensils | high | 16 | 10 | 6 | 0 |
| `stagnant_water` | Standing water | high | 14 | 10 | 8 | 6 |
| `pest_evidence` | Signs of pests | high | 25 | 20 | 15 | 10 |
| `open_drain` | Open drain or leaking pipe | moderate | 12 | 8 | 10 | 12 |

**Checklist** (6 vendor-declared, FSSAI-flavoured): covered waste bin within the stall; clean water available for washing; food handled with clean hands or tongs; utensils washed and stored covered; food stored off the ground; no stray animals observed near the stall.

Every result screen carries the persistent note: **"AI-assisted, not an official certification."**

---

## 8. `integrations/cv_client.py` — the swap boundary

```python
@dataclass
class Detection:
    label: str          # indicator code
    raw_label: str      # what the provider actually saw
    confidence: float
    bbox: tuple[int, int, int, int] | None
    source: str         # "onnx_yolo" | "heuristic"

class CvProvider(Protocol):
    name: str
    def detect(self, image_bgr: np.ndarray, view: ViewCategory) -> list[Detection]: ...

def run_detection(image_bytes, view) -> CvResult   # dispatches on settings.CV_PROVIDER
```

- `HeuristicProvider` — Canny edge density (clutter), Laplacian texture, brightness/contrast, large low-saturation regions (stagnant water), high-frequency blob density (waste). **Deterministic**, so it is fully testable, and it needs no model file.
- `OnnxYoloProvider` — letterbox preprocessing → `onnxruntime.InferenceSession` → decode YOLOv8 head → NMS → `_COCO_TO_INDICATOR` mapping.
- Errors: `CvModelUnavailable` (no file) and `CvInferenceError`, both surfaced as a scan-style `503` with a vendor-safe message, never a 500.

Swapping in a real model changes only this file — plus the seeded `cv_labels`, which is data.

---

## 9. Mobile UI

**Guided capture** (`hygiene/new`) — one screen per view, driven by the same `CameraCapture` built in Phase 2:

```
Step 2 of 4          ●●○○
Now photograph the storage area
Where dry goods and containers are kept
[ camera viewfinder ]
```

- Reuses `CameraCapture` (camera + guide overlay + gallery fallback + HTTPS caveat handling).
- Progress indicator; completed views collapse to thumbnails with a retake affordance.
- After the 4th upload, a "Checking your stall…" state while detection and scoring run.

**Results** (`hygiene/[checkId]`) — score dial, per-view findings, detected indicators with confidence, checklist answers, and the "AI-assisted, not an official certification" note pinned at the bottom.

**History** (`hygiene`) — reverse-chronological cards: date, score chip (colour-banded), indicator count, thumbnail strip. Mobile-friendly, tappable through to results. The bottom-nav **Hygiene** tab (currently rendered disabled) becomes live.

---

## 10. API surface

| Method | Path | Role |
|---|---|---|
| `POST` | `/api/v1/hygiene/checks` | vendor — create a draft check |
| `POST` | `/api/v1/hygiene/checks/{id}/images` | vendor — upload one view (multipart + `view_category`) |
| `POST` | `/api/v1/hygiene/checks/{id}/checklist` | vendor — submit checklist answers |
| `POST` | `/api/v1/hygiene/checks/{id}/complete` | vendor — score once all 4 views present |
| `GET` | `/api/v1/hygiene/checks` | vendor (own stalls) / reviewer (all) |
| `GET` | `/api/v1/hygiene/checks/{id}` | owner vendor or reviewer |
| `GET` | `/api/v1/hygiene/indicators` | reviewer — the catalog |

Role scoping reuses the `_vendor_stall_ids` / `get_stall_for_reader` helpers from Phases 1–2 so "may I see this" cannot drift between resources.

---

## 11. Dependencies

| Package | Verified | Purpose |
|---|---|---|
| `onnxruntime>=1.20` | ✅ 1.30.0 cp314 wheel | YOLO-family inference, no torch |
| `opencv-python-headless` | already installed | preprocessing, hashing, heuristics |
| `numpy` | already installed | array work |

No new dependency for the heuristic path. **No torch, no ultralytics, no `opencv-python`.**

---

## 12. Tests

| File | Covers |
|---|---|
| `test_hygiene_hashing.py` | aHash/dHash stability, Hamming distance, duplicate rejection |
| `test_hygiene_coverage.py` | all 4 required, missing-view messaging, partial states |
| `test_hygiene_indicators.py` | detections → findings, **per-view penalties incl. waste-in-waste-area = 0** |
| `test_hygiene_scoring.py` | 70/30 formula, clamping, severity multipliers, versioning |
| `test_cv_heuristic.py` | determinism, synthetic images for each signal |
| `test_cv_onnx.py` | letterbox shape, NMS correctness, `CvModelUnavailable` when the file is absent — **no real model needed** |
| `test_hygiene_pipeline.py` | end-to-end on SQLite with the detector mocked |

The ONNX tests use synthetic tensors and assert preprocessing/NMS/decode logic. They do **not** require a downloaded model, so CI stays hermetic.

---

## 13. Explicitly out of scope

Reviewer dashboard hygiene views (Phase 4 wiring), the public QR/consumer page, adaptive monitoring intervals, the hygiene map, the anti-manipulation pipeline, official certification, and any claim that a hygiene score is authoritative.

---

## 14. Risks

| Risk | Mitigation |
|---|---|
| Placeholder detector has unknown real-world precision | Stated openly in docs and in the UI note; `heuristic` is the default; the COCO mapping is one table |
| Vendor mis-tags a view | Perceptual-hash duplicate guard; reviewer sees all four photos |
| Vendor games the checklist (30% of score) | Visual weight is 70%; indicator `view_penalties` cannot be self-declared |
| No `.onnx` file present | Clear `CvModelUnavailable` + export instructions; heuristic provider works regardless |
| 4 images per check is heavier than Phase 2 | Still synchronous (heuristic ~200 ms, ONNX ~150 ms/img); `workers/README.md` already documents the async path |
| `stalls.hygiene_score` drift from `hygiene_scores` | Updated in the same transaction as the score row |

---

## 15. Proposed commit sequence

1. `feat: hygiene models, migration, indicator + checklist seed`
2. `feat: cv_client — provider interface, heuristic + ONNX YOLO providers`
3. `feat: hygiene service — coverage, duplicate guard, scoring`
4. `feat: hygiene API endpoints`
5. `feat: mobile guided capture, results, and history UI`
6. `test: hashing, coverage, indicators, scoring, cv providers, pipeline`

---

**Awaiting your approval.** Two things I'd particularly like a steer on before I start, since both are cheap to change now and expensive later:

1. **Detections as JSONB on `stall_images`** (§5) — keeps to your four tables. Say the word if you'd rather have a fifth `hygiene_detections` table for Phase 4 reviewer analytics.
2. **The COCO stand-in mapping** (§3) is weak by construction. If you'd prefer, I can ship `CV_PROVIDER=heuristic` as the *only* path for now and add the ONNX provider behind the interface without wiring the COCO mapping at all — less code, and no risk of anyone mistaking a detected `cup` for a hygiene finding.
