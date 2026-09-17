# Implementation Plan — Phase 6: Local IndicTrans2 Translation

Status: **DECISIONS LOCKED (§0) — awaiting your go-ahead. No code has been written.**

Replaces: the Google Cloud Translation half of `integrations/translate_client.py`.
Does **not** touch: Google Cloud Vision OCR (`integrations/ocr_client.py`).

---

## 0. Decisions locked (from your answers)

1. **You download the model; I wire up the rest.** No token in `.env`. The
   local directory *is* the pin, which also retires most of the
   `trust_remote_code` supply-chain concern — the files are frozen on disk.
2. **Port the pre/post-processor in pure Python.** No Cython, no MSVC; ~25
   packages dropped.
3. **Lazy, thread-safe, single-flight model load.** No FastAPI lifespan. The
   test suite, and any dev server that never translates, never load the model.
4. **`TRANSLATION_NUM_BEAMS=5`**, matching the model card. Configurable; the
   docs will name `1` as the lever if CPU latency bites.

### What the download actually needs — measured, not assumed

The repo reports `usedStorage` of **3.89 GB**, but that counts three
near-duplicate weight sets: `model.safetensors`, `pytorch_model.bin`, and the
fairseq `model.SRC` / `model.TGT` checkpoints. We load safetensors and never
read the other two.

| Fetch | Skip | Why |
|---|---|---|
| `model.safetensors`, `*.json`, `*.py`, `LICENSE`, `README.md` | `pytorch_model.bin`, `model.SRC`, `model.TGT` | duplicate weights; fairseq checkpoints transformers never reads |

That is roughly **1.3 GB instead of 3.9 GB**. Exact commands in §13.

Pinned revision: `173b94239f7c38886b2747b8d4a5db771a7e1232` (repo last modified
2025-05-02). I will record this hash in the docs so the translation behaviour
we ship is auditable.

---

## 0b. SPIKE RESULTS — Step 3, actually run

Run against the real downloaded model on Python 3.14.7, CPU, Windows.
**The spike changed four things in this plan.** Recording them here rather
than quietly editing the sections above.

### What works

| Check | Result |
|---|---|
| Tokenizer load | 0.27s, `IndicTransTokenizer`, src vocab 32322 / tgt 122672 |
| Model load | **0.56s** cold, 211.8M params |
| `wheat flour` → Hindi | **गेहूं का आटा** |
| `wheat flour` → Marathi | **गव्हाचे पीठ** |
| Batch of 3, one `generate()` call | 4.10s hi / 5.34s mr |
| RSS after load / peak | 385 MB / 1180 MB |

### Delta 1 — `transformers` must be `==4.51.3`, not `<5`

The remote modelling code does `past_key_values[0][0].shape[2]`, i.e. it wants
the **legacy tuple** KV cache. Newer transformers hand it a `Cache` object and
it dies with `AttributeError: 'NoneType' object has no attribute 'shape'`.

Probed every candidate, in a scratch venv, so the project venv was untouched:

| transformers | `use_cache=True` |
|---|---|
| 4.38.2 | OK |
| 4.44.2 | **not installable** — wants a `tokenizers` with no wheel, pip falls back to compiling Rust and fails |
| 4.49.0 | OK |
| **4.51.3** | **OK — newest working; now pinned** |
| 4.55.4 | FAIL `KeyError: 'Cache only has 0 layers, attempted to access layer with index 0'` |
| 4.56.2 / 4.57.0 / 4.57.6 | FAIL `AttributeError: 'NoneType'` |

So the cache breaks in the 4.52–4.55 window, and 4.57.6 — the version I
installed in Step 1 — was on the wrong side of it. §7's `<5` was too loose.
**Do not upgrade past 4.51.3 without re-running the cache probe**; that goes in
the docs, because the failure is a runtime crash on first translation, not an
install-time error.

Why it matters: `use_cache=True` on 4.51.3 is worth real time, and it removes
the O(n²) fallback entirely.

| Case | 4.51.3 + cache | 4.57.6 + no cache |
|---|---|---|
| realistic sentence, beams=5 | **2.25s** | 4.65s |
| 43-word sentence, beams=5 | **7.53s** | 24.88s |

The 24.88s figure would have put the 43-word case uncomfortably close to the
30s timeout. At 7.53s it is not a concern.

### Delta 2 — `sentencepiece` is required, and I missed it

`tokenization_indictrans.py` line 7 is `from sentencepiece import SentencePieceProcessor`
at module scope, and `_load_spm` calls `SentencePieceProcessor(model_file=path)`.
§7 never listed it. Installed: `sentencepiece==0.2.2` (cp314 wheel exists).

### Delta 3 — §0's file scoping was wrong, and it would have blocked the build

I told you to skip `model.SRC` / `model.TGT` as "~2.6 GB of weights we never
read", inferring from the filenames. **They are SentencePiece model protos,
0.8 MB and 3.3 MB, and the tokenizer cannot load without them.** Fetched
separately. Measured reality:

| File | Size | Verdict |
|---|---|---|
| `model.safetensors` | 1098.4 MB | needed |
| `pytorch_model.bin` | 1098.6 MB | duplicate — correctly skipped |
| `model.SRC` / `model.TGT` | 0.8 / 3.3 MB | **needed** |
| repo total | 2205.2 MB | not 3.89 GB — that figure counted historical blobs |

Skipping `pytorch_model.bin` saves 1.1 GB, not 2.6 GB. The lesson is that I
inferred file roles from their names instead of reading the code that loads
them; the download only succeeded because the failure was cheap to diagnose.

### Delta 4 — language codes verified from source, not inferred

`LANGUAGE_TAGS` in `tokenization_indictrans.py` is a frozen set containing
`eng_Latn`, `hin_Deva` and **`mar_Deva`** — §4's one flagged uncertainty is
closed. Better: `_src_tokenize` is

```python
src_lang, tgt_lang, text = text.split(" ", 2)
assert src_lang in LANGUAGE_TAGS, f"Invalid source language tag: {src_lang}"
```

which both **confirms the `f"{src} {tgt} {text}"` prefix format** and means the
tokenizer validates tags for us — an un-tagged string raises `ValueError`, a
bad tag raises `AssertionError`. Our preprocessor still validates first, so the
error is ours and actionable rather than a stack trace through remote code.

Tags are real single tokens: `eng_Latn hin_Deva wheat flour` → `[4, 15, 5680, 2912, 2]`.

### Delta 5 — entity masking is a safety net, not load-bearing

§6 justified digit protection because "a distilled model will happily
transliterate digits". Measured, unmasked: `32` and `500` both survived
(`... 32 प्रतिशत संतृप्त वसा और 500 मिलीग्राम सोडियम ...`). So the motivating
claim was overstated. I will keep a light digit guard — the reference does it,
and one lucky sample is not a guarantee — but it is defence in depth, not the
thing standing between us and mangled labels. Stated plainly rather than left
to look load-bearing.

### One operational gotcha, for logging

The Windows console is cp1252 and **cannot encode Devanagari** — a successful
translation initially presented as `UnicodeEncodeError`. Two consequences:
spikes/tests need `PYTHONIOENCODING=utf-8`, and the app must never let
translated text reach a cp1252 log handler. We do not log translated text
anyway (it is user content), but this is why.

### Verification status

The pipeline is **proven end-to-end on real weights and real inference**, which
no prior phase managed. Not yet proven: the HTTP endpoint path, and Google
Vision (still needs your credentials).

### Delta 6 — entity masking is dropped from the design (Delta 5 corrected)

Delta 5 said masking was defence in depth. Measured, it is a net **risk**, so
it comes out. Same sentence, both languages, three sentinel styles:

| Sentinel | Hindi result | Verdict |
|---|---|---|
| *(no masking)* | `32 प्रतिशत ... 500 मिलीग्राम` | ✅ digits preserved natively |
| `__N0__` | `% @ N0 @ %` | ❌ mangled |
| `⟦0⟧` | `0` / `1` — **brackets stripped** | ❌ fails *silently* |
| `X0X` / `X1X` | `X0X ... X1X` | ✅ survived |

The `⟦0⟧` failure is the dangerous one: the brackets vanish, so the placeholder
becomes indistinguishable from a real number, unmasking finds nothing, and we
would ship a label with wrong quantities while believing it was protected.
Masking was solving a problem that does not exist, and could have created a
worse one.

**Replacement: detect, don't transform.** `digits_preserved(source, translated)`
compares the digit multisets and logs a warning when they differ. It is a pure
function, testable with no model, and it cannot corrupt anything — it only
observes. §6's masking steps 3 and 4 are deleted.

Open product question, deliberately not decided here: when digits are lost,
should the string fall back to English? The detection makes that a one-line
policy change later; today it logs, because the measurement says this path is
rare and I would rather not invent a new user-visible state on a hunch.

---

## 1. What I found by inspection

Read in full: `integrations/translate_client.py`, `integrations/ocr_client.py`,
`core/config.py`, `services/products/scan_service.py` (translate call sites),
`tests/test_translate_fallback.py`, `tests/test_scan_pipeline.py`,
`main.py`, `requirements.txt`, `.env`, `.env.example`, `app/workers/README.md`,
and the frontend's `lib/types.ts` + `components/scan/ScanResultCard.tsx`.

**The abstraction is already in the right place.** `translate_many(texts, target)`
already takes a *batch* of strings and returns a list of `TranslationResult`,
and every test monkeypatches the single seam `translate_client._run_provider`.
So this is a provider swap behind an existing interface, not a redesign.

Google Translate's actual blast radius, measured rather than assumed:

| File | What is Google-specific |
|---|---|
| `requirements.txt:22` | `google-cloud-translate==3.15.2` |
| `core/config.py:26` | `GOOGLE_TRANSLATE_API_KEY` |
| `translate_client.py:99-142` | `_translate_v3`, `_translate_v2`, `_run_provider` dispatch |
| `.env:42`, `.env.example:42` | `GOOGLE_TRANSLATE_API_KEY=""` |
| `tests/test_translate_fallback.py:220-229` | `TestCredentialDispatch` (the only test touching Google auth) |

Everything else — the cache, the batching, the fallback policy, the
`TranslationResult` contract, `scan_service`, both route layers, and the whole
frontend — is provider-agnostic and stays untouched. The frontend expects
`explanation_translated`, `language_code`, `translation_failed`; all three keep
their exact current meaning.

**Vision/Translate credential separation, which you asked about specifically.**
`GOOGLE_APPLICATION_CREDENTIALS` *is* used by Vision (ADC via
`vision.ImageAnnotatorClient()`) and **stays**. `GOOGLE_CLOUD_PROJECT` is read
by this codebase **only** in `translate_client._translate_v3` — Vision does not
reference it. I will keep the setting declared (harmless, and you asked me not
to remove it) but correct its comment to say it is no longer required by
translation. After this change, translation requires **zero** Google
credentials.

---

## 2. Two real compatibility problems, both measured

I dry-ran every dependency against this exact interpreter (Python 3.14.7,
Windows) instead of trusting release notes. Results:

**Good news — the ML stack is fine on 3.14.7.** I built a scratch venv off the
project's Python and installed the real stack:

```
torch 2.14.0+cpu   transformers 4.57.6   tokenizers 0.22.2   safetensors 0.8.0
sentencepiece 0.2.2 (cp314 win_amd64 wheel exists)
torch.rand(2,3) @ .T  ->  works
```

Every one of those has a wheel for cp314 on Windows. `tokenizers` ships
`cp39-abi3`, so it is version-proof forward. **No compiler is needed for the
model stack.** This is the finding that makes local IndicTrans2 viable at all.

### Problem 1 — `IndicTransToolkit` cannot be installed on this machine

The reference pre/post-processor (`IndicProcessor`) lives in
`IndicTransToolkit`, whose processor is **Cython** (`processor.pyx`, 781 KB of
generated `processor.c`). Its published wheels are:

- cp310, cp311, cp312, cp313, pp310 — macOS arm64, manylinux, musllinux only
- **no cp314 wheel, no abi3 wheel, no pure-Python wheel**
- **no Windows wheel at all**, for any Python version

So on this project it is sdist-only, and would have to compile Cython through
MSVC. (VS 2022 is present on this machine, but `cl.exe` is not on `PATH`, and a
`.c` generated against older CPython headers is not a safe bet for 3.14.) It also
drags a runtime toolchain in as hard dependencies: `sphinx`,
`sphinx-argparse`, `sphinx_rtd_theme`, `alabaster`, `docutils`, `pandas`,
`lxml`, `Morfessor`, `cloudpickle`, `tabulate` — roughly 25 packages, most of
which are documentation and evaluation tooling with no role in inference.

**My recommendation (see Q2): do not use the toolkit.** Port its algorithm
instead. That is more defensible than it sounds: `processor.pyx` is public and
MIT-licensed, so it can be read as the *specification* and our port unit-tested
against fixtures derived from it — rather than invented. Our inputs are also
much narrower than what the reference machinery exists for: explanation
sentences, recommendation strings, and ingredient names. It is not long
documents full of dates, URLs and abbreviations.

### Problem 2 — the model repo is gated

`https://huggingface.co/api/models/ai4bharat/indictrans2-en-indic-dist-200M`
reports `"gated": "auto"`, and an unauthenticated fetch of
`tokenization_indictrans.py` returns **HTTP 401**.

"auto" gating means: sign in, accept the model's terms on the model page, then
any read token works. There is no way around it and no trustworthy ungated
mirror I would point you at. **Resolved: you download it (§0.1).** I never hold
your token, and nothing about translation needs it at runtime.

Two consequences worth stating plainly:

- The model **cannot** be downloaded on a fresh clone without an authenticated
  one-time setup. "Works offline after first download" is true, but the first
  download is not turnkey — it is a documented manual step, not something the
  app does for you.
- The model uses `trust_remote_code=True`, i.e. it executes Python shipped in
  the model repo. Because we load from a local directory rather than the Hub
  cache, those files are frozen on disk and cannot change under us. The
  auditable identity of what we run is the commit hash in §0.

**License: MIT**, confirmed from both the model card and the repo metadata — so
redistribution and commercial use are permitted, with the copyright notice
preserved. I will add the attribution notice rather than leave it implicit.

---

## 3. Architecture — smallest change that achieves the goal

Mirror the provider pattern this codebase already uses twice
(`ocr_client._PROVIDERS`, `cv_client._PROVIDERS`).

```
scan_service.translate_many(texts, "hi")
        │
        ▼
integrations/translate_client.py        ← public API UNCHANGED
    cache · batching · fallback policy · provider dispatch by TRANSLATION_PROVIDER
        │
        ▼
integrations/indictrans2.py             ← NEW: local model runtime
    lazy thread-safe load · single-worker executor · device · timeout
        │
        ▼
integrations/indic_text.py              ← NEW: pure Python, no torch
    language tags · sentence split · entity masking · post-cleanup
```

Splitting `indic_text.py` out is deliberate: it makes the text handling
unit-testable with **no model, no torch and no download**, which is what keeps
the default test suite fast and offline.

### Files

| File | Change |
|---|---|
| `app/integrations/translate_client.py` | UPDATED — provider registry; `_run_provider` kept as the seam; Google paths deleted |
| `app/integrations/indictrans2.py` | NEW — model lifecycle + inference |
| `app/integrations/indic_text.py` | NEW — pure pre/post-processing, lang codes |
| `app/core/config.py` | UPDATED — translation settings; drop `GOOGLE_TRANSLATE_API_KEY` |
| `requirements.txt` | UPDATED — remove `google-cloud-translate`, add `torch`/`transformers` |
| `.env`, `.env.example` | UPDATED — drop the API key; add provider/model settings |
| `tests/test_translate_fallback.py` | UPDATED — `TestCredentialDispatch` → provider config tests |
| `tests/test_indic_text.py` | NEW — pre/post-processing, no model needed |
| `tests/test_indictrans2_runtime.py` | NEW — load/device/timeout/failure, **mocked model** |
| `tests/test_indictrans2_model.py` | NEW — real inference, **opt-in marker** |
| `README.md`, `docs/translation.md` | UPDATED / NEW — setup, Windows commands, attribution |

**Not touched:** `ocr_client.py`, `scan_service.py`, `schemas/`, `api/`,
anything in `frontend/`.

---

## 4. Language codes

`indic_text.py` owns one explicit map — no guessing at call sites:

| App code | IndicTrans2 tag | Status |
|---|---|---|
| `en` | `eng_Latn` | source; confirmed on the model card |
| `hi` | `hin_Deva` | confirmed on the model card |
| `mr` | `mar_Deva` | **verify against the repo's supported-language list before wiring** |

The public API keeps `"en"`/`"hi"`/`"mr"` (`settings.SUPPORTED_LANGUAGES`
unchanged); mapping is internal. An unmapped target returns the original English
with a warning — never an exception, consistent with the existing fallback
policy. I flag `mar_Deva` as unverified only because the gated 401 blocked me
from reading the file; `hin_Deva`/`eng_Latn` on the card make the FLORES-200
scheme unambiguous, and the spike confirms it before any code depends on it.

---

## 5. Model lifecycle

- **Lazy, single-flight load.** There is no FastAPI lifespan in `main.py`
  today. A module-level singleton guarded by a `threading.Lock`, so concurrent
  first requests cannot race into two model instances. Cold load is a one-time
  cost, and — the real reason — **the test suite and any dev server that never
  translates never load a model at all**.
- **Loaded once, reused forever.** Never per request.
- **Device:** `cuda` if `torch.cuda.is_available()` and `TRANSLATION_DEVICE`
  is `auto`, else `cpu`. CPU is fully supported; CUDA is never required.
- **dtype:** `float32` on CPU. The model card's `torch_dtype=torch.float16` is
  GPU guidance — fp16 on CPU is slower and unsupported for some ops. I will not
  copy it blindly. No `attn_implementation` (no flash-attn on CPU).
- **Cache:** `TRANSLATION_MODEL_CACHE_DIR` (default `var/models/hf`), passed as
  `cache_dir=` and mirrored into `HF_HOME`. Downloaded once; afterwards a
  `TRANSLATION_OFFLINE` switch sets `HF_HUB_OFFLINE=1` so a network outage can
  never turn a scan into a hang.
- **Loaded from a local directory** (§0.1), so the pinned revision is a
  property of the files on disk. `TRANSLATION_MODEL` accepts either a Hub repo
  id or a filesystem path; a path is what the docs recommend and what the
  config defaults to.

### Concurrency and the timeout, honestly

`Product.` scan endpoints are plain `def`, so FastAPI already runs them in a
threadpool — the event loop is not at risk, and no async rewrite is needed.

Inference is dispatched to a **`ThreadPoolExecutor(max_workers=1)`**:

- one worker **serialises inference**, so N concurrent scans cannot start N
  CPU-bound decodes and thrash the box — they queue;
- the caller waits at most `TRANSLATE_TIMEOUT_SECONDS` (now 30) via
  `future.result(timeout=...)`, then degrades to English with a warning.

One caveat I will document rather than paper over: **Python cannot cancel a
running thread.** On timeout the caller returns the fallback immediately, but
that one inference finishes in the background. With `max_new_tokens` capped and
the queue serialised, the work is bounded — it is not an unbounded leak. This is
the standard trade for in-process local inference; a process-pool would fix it
and is not worth its cost here.

---

## 6. Pre/post-processing (our own, since the toolkit is out)

Ported from `processor.pyx` as spec, in plain Python:

1. **Language tags** — prefix the tag pair, once per segment. Exact placement
   confirmed against the tokenizer in the spike.
2. **Sentence splitting** — split on `।`, `?`, `!`, `.` so long text becomes
   several short decodes instead of being silently truncated. This is what
   makes the "long text" test meaningful rather than a truncation assertion.
3. **Entity masking** — protect numbers, decimals, percentages and
   number+unit pairs (`500g`, `1.5%`) behind sentinels, restore them
   afterwards. A distilled model will happily transliterate digits, and this
   project's whole domain is quantities on food labels. This is a reduced
   version of the reference machinery and I will say so in the docs.
4. **Post-cleanup** — unmask, strip an echoed tag, collapse whitespace, and
   satisfy an `IndicProcessor.postprocess_batch`-style contract.
5. **Length guard** — drop over-long segments rather than emit garbage, and
   count that as a per-segment fallback.

**Batching:** `translate_many` already batches, and the model takes a real
batch, so N uncached strings are one `generate()` call. The existing LRU cache
(512 entries, per target language) is kept as-is — it is already correct, and
in this domain explanation text repeats heavily across scans.

### Beams

The model card uses `num_beams=5`, and per §0.4 that is the default. On CPU it
is roughly a 5× decode cost for a small quality gain, so `TRANSLATION_NUM_BEAMS`
is a real setting rather than a constant, and the docs will say plainly that `1`
is the lever if per-scan latency on a vendor's phone matters more than the last
few percent of translation quality.

---

## 7. Configuration

```ini
# OCR — unchanged. Vision still needs these.
OCR_PROVIDER="google_vision"
GOOGLE_APPLICATION_CREDENTIALS=""
GOOGLE_CLOUD_PROJECT=""            # no longer used by translation

# Translation — local, no Google credentials
SCAN_TRANSLATION_ENABLED=true
TRANSLATION_PROVIDER="indictrans2"
TRANSLATION_MODEL="ai4bharat/indictrans2-en-indic-dist-200M"
TRANSLATION_MODEL_REVISION="<pinned commit>"
TRANSLATION_MODEL_CACHE_DIR="var/models/hf"
TRANSLATION_DEVICE="auto"
TRANSLATION_NUM_BEAMS=5
TRANSLATION_MAX_NEW_TOKENS=256
TRANSLATION_MAX_CONCURRENCY=1
TRANSLATION_OFFLINE=false
TRANSLATE_TIMEOUT_SECONDS=30
```

`GOOGLE_TRANSLATE_API_KEY` is **removed**. There is no `HF_TOKEN`: the model is
downloaded by hand (§13) and read from disk, so translation needs **no network
and no credential at runtime at all**.

---

## 8. Failure behaviour — the existing contract, preserved

The rule that a translation problem must never cost a vendor their scan verdict
is already implemented and tested. It does not change. New error classes
(`ModelDownloadError`, `ModelInitializationError`, `ModelInferenceError`) map
onto the existing degrade path: original English, `translated=False`, a
`warning`, `translation_failed=True`. An unsupported language does the same. If
the model is absent and we are offline, the app still boots and scans still
work — in English, visibly degraded, with an actionable log line. **We never
claim a translation succeeded when it did not**, and never silently fall back to
Google.

---

## 9. Tests

Default suite stays **fast, offline, and model-free**:

| Area | Cases |
|---|---|
| Pre/post | empty, whitespace-only, long text splits, entity round-trip, tag not echoed, unsupported language, tag placement |
| Runtime | lazy load happens once, device selection, CPU path, timeout → degrade, inference exception → degrade, disabled → no call, provider config, model-missing + offline |
| Scan pipeline | existing `test_scan_pipeline.py` re-run unchanged; add an end-to-end case with a **stubbed** provider |
| Model (opt-in) | real English→Hindi and English→Marathi return non-empty, script-correct output — `@pytest.mark.translation_model`, deselected by default |

The model-dependent tests are opt-in because **the default suite must not
download ~1.2 GB**. Following you: no hard-coded expected translation strings;
assertions are non-empty, correct script, preserved numerals.

---

## 10. Verification

I can do: the full backend suite, the new translation tests, the scan-pipeline
tests, the frontend suite, and a project-wide search for Google Translate
references (I already have the inventory in §1).

I **cannot** do without you: live Google Vision OCR (needs your credentials),
and the first gated model download (needs your HF token). I will not claim
either passed if it has not run. I will report the model-size/RAM/latency
numbers that the spike actually measures, not estimates.

---

## 11. Risks

| Risk | Mitigation | Residual |
|---|---|---|
| Our preprocessor diverges from the reference | Port `processor.pyx` as spec; fixture-test each stage | Real; documented as a reduced port |
| Remote code incompatible with transformers 4.57.6 | Spike first; fall back to a 4.3x–4.4x pin if needed | Unproven until the spike — this is the biggest unknown |
| Gated download blocks setup | Q1; documented one-time Windows steps | Needs your action |
| CPU latency per scan | Serialised worker, sentence-sized decodes, LRU cache, configurable beams, warmup path | ~1–3 s/scan cold, expect ~0 cached |
| RAM (torch + model resident) | fp32, one instance, lazy | ~1.5–2.5 GB |
| Timeout cannot cancel a thread | Bounded decode, `max_workers=1` | Documented, not fixed |
| `trust_remote_code` supply chain | Pin `revision` to a commit | Accepted |
| Vision regression | Vision files untouched; OCR tests re-run | Live check needs your creds |

---

## 12. Proposed commit sequence

1. `feat: pure-python IndicTrans2 text pre/post-processing + language tags`
2. `feat: local IndicTrans2 runtime (lazy load, device, batching, timeout)`
3. `refactor: translate_client provider registry; remove google-cloud-translate`
4. `chore: config, requirements, env for local translation`
5. `test: preprocessor, runtime (mocked), opt-in real-model inference`
6. `docs: local translation setup, Windows steps, attribution; README env table`

---

## 13. Order of work

I do not want to build on an unverified model load, so the spike gates the
build. Nothing below writes application code until step 3 reports back.

**Step 1 — me: dependencies only.** Pin and install `torch` + `transformers<5`
into the project venv. No application code changes.

**Step 2 — you: accept the terms, then download.** One time.

1. Sign in and click *Agree and access repository* at
   `https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M`
2. Then:

```bash
cd /d/fuuk/Smart_Street_Food_Safety_Ai/backend

venv/Scripts/hf.exe auth login

venv/Scripts/hf.exe download ai4bharat/indictrans2-en-indic-dist-200M \
  --revision 173b94239f7c38886b2747b8d4a5db771a7e1232 \
  --local-dir var/models/indictrans2-en-indic-dist-200M \
  --include "*.json" "*.py" "model.safetensors" "LICENSE" "README.md"
```

Deliberately **not** fetched: `pytorch_model.bin`, `model.SRC`, `model.TGT`
(~2.6 GB of weights we never read — see §0). If you would rather not use the
CLI at all, the model page's *Files* tab lets you download those same files
individually.

**Step 3 — me: spike, then report before building.** Load from the local
directory and confirm:

1. the remote code loads under transformers 4.57.6;
2. "wheat flour" → Hindi and → Marathi, for real, output in the right script;
3. `mar_Deva` is the repo's actual Marathi tag;
4. measured cold-load time, on-disk size, RSS, and per-scan latency.

If (1) fails, the fallback is a transformers 4.3x pin, which I will bring back
to you before applying rather than silently re-pinning.

**Step 4 — me: build** the six commits in §12, then run verification (§10).
