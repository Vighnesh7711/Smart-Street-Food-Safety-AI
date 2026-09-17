# Background workers

Empty by design. Phase 2 runs the scan pipeline **synchronously** inside the
request, and this directory documents how to change that when it stops being
the right call.

## Why synchronous today

A scan makes exactly one network call (Cloud Vision OCR) plus, once per
uncached explanation, one inference pass over the local IndicTrans2 model.
Typical end-to-end latency is well under the point where a vendor notices. Synchronous means:

- one round trip, no job table, no polling endpoint, no worker deployment
- the mobile UI's loading state maps directly onto the request
- failures surface immediately with an accurate HTTP status

## When to move to a worker

Move when any of these becomes true:

- **OCR latency grows** — swapping to a local model (EasyOCR on CPU is
  roughly 2–5 s per label) or scanning many labels at once.
- **Bursty load** — a market full of vendors scanning at opening time. A
  synchronous endpoint holds a worker thread for the whole pipeline.
- **You add pipeline stages** that are slower or need retries — the hygiene
  CV phase (scope item 2) will run multiple images per submission.
- **You want retries on provider outages** rather than asking the vendor to
  tap again.

## The upgrade path

The pipeline is already shaped for this. `services/products/scan_service.py`
is a pure function of its inputs:

```python
scan_label(db, *, stall, user, image_bytes, target_language) -> ScanOutcome
```

To go asynchronous:

1. **Add a `scan_jobs` table** — `id`, `stall_id`, `status`
   (`pending`/`running`/`done`/`failed`), `scan_image_path`, `result_id`,
   `error`, `created_at`, `started_at`, `finished_at`.

2. **Change the endpoint** — `POST /products/scan` stores the image, inserts
   a `pending` job, enqueues it, and returns `202 {job_id}`.

3. **Add a worker** in this directory that pops a job, calls the existing
   `scan_label`, and writes the outcome:

   ```
   workers/
   ├── runner.py        # entrypoint: consume queue -> scan_label()
   └── queue.py         # Redis/RQ, Celery, or a LIST in PostgreSQL to start
   ```

   The image is already persisted to `SCAN_UPLOAD_DIR` before OCR, so the
   worker needs only the file path — no need to pass bytes through the queue.

4. **Add `GET /products/scan/{job_id}`** returning `pending`/`running`/`done`
   plus the `ScanResultRead` once finished, and poll it from the mobile UI
   (every ~1.5 s, backing off).

5. **Keep the synchronous path** behind a flag. It is genuinely better for
   the common case, and the reviewer dashboard's bulk views will still want
   direct reads.

## What does NOT need to change

`status_engine`, `matching`, `normalization`, `ingredient_extraction`,
`explanation`, `image_quality`, `ocr_client`, and `translate_client` are all
pure or stateless and are called identically from a worker. Only the
orchestration and the persistence boundary move.
