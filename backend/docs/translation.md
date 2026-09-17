# Local translation with IndicTrans2

The vendor-facing translation step runs **AI4Bharat IndicTrans2** locally, in
the backend process. No API key, no quota, no billing, and no label text
leaving the machine.

- Language pairs: **English → Hindi**, **English → Marathi**
- Model: `ai4bharat/indictrans2-en-indic-dist-200M` (distilled, 211.8M params)
- Licence: **MIT** — see [Attribution](#attribution)
- Runtime: PyTorch on **CPU** (CUDA used automatically when present)

---

## Why Google Cloud Translation was removed

Translation used to call `google-cloud-translate`, either with a service
account or an API key. Three reasons it went:

1. **It required billing and a credential** to do something that a 1.1 GB
   local model now does for free. Translation was the only part of the scan
   that could fail for an administrative reason.
2. **It sent label text to a third party.** Ingredient lists and brand names
   from small vendors are not sensitive in the way health data is, but they
   are not ours to ship off either, and OCR is the only remaining reason this
   project needs a cloud account at all.
3. **It made the app undeployable without Google.** A vendor scanning at a
   market with no billing account enabled got English back.

Google Cloud **Vision** still performs OCR. That is a deliberate, documented
tradeoff (see the main README): PaddleOCR publishes no wheel for Python 3.14,
and Tesseract needs an unmanaged system binary. The two no longer share any
credential — `GOOGLE_TRANSLATE_API_KEY` is gone, and the app translates
happily with no Google credentials configured at all.

---

## Installation

```bash
cd backend
./venv/Scripts/python.exe -m pip install -r requirements.txt
```

That pulls `torch`, `transformers==4.51.3` and `sentencepiece`. All three have
wheels for Python 3.14 on Windows, so **no C compiler is needed**.

> `IndicTransToolkit`, the official pre/post-processor, is deliberately **not**
> used. Its processor is a Cython extension with no cp314 wheel, no abi3 wheel,
> and no Windows wheel at all, so installing it would mean building C through
> MSVC — and it pulls Sphinx, pandas, lxml and Morfessor in as *runtime*
> dependencies. `app/integrations/indic_text.py` is a plain-Python port of the
> parts actually needed.

---

## First model download (one-time, ~1.1 GB)

The model repository is **gated**. Signing in is not enough; access must be
granted to your account, or every download fails with
`403 GatedRepoError`.

**1.** Sign in and click **Agree and access repository** at
<https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M>

**2.** From `backend/`:

```bash
venv/Scripts/hf.exe auth login

venv/Scripts/hf.exe download ai4bharat/indictrans2-en-indic-dist-200M \
  --local-dir var/models/indictrans2-en-indic-dist-200M \
  --include "*.json" "*.py" "model.safetensors" "model.SRC" "model.TGT" \
            "LICENSE" "README.md"
```

### What is downloaded, and what is not

| File | Size | Needed? |
|---|---|---|
| `model.safetensors` | 1098.4 MB | ✅ the weights |
| `pytorch_model.bin` | 1098.6 MB | ❌ duplicate of the above |
| `model.SRC`, `model.TGT` | 0.8 MB, 3.3 MB | ✅ **SentencePiece protos** |
| `dict.SRC.json`, `dict.TGT.json` | 0.6 MB, 3.4 MB | ✅ vocabularies |
| `*.py`, `*.json` config | < 0.1 MB | ✅ remote code + config |

Skipping `pytorch_model.bin` halves the download. **Do not skip
`model.SRC`/`model.TGT`**: the names suggest fairseq checkpoints, but
`tokenization_indictrans.py` loads them with
`SentencePieceProcessor(model_file=path)` and the tokenizer cannot start
without them.

### Version caveat

The upstream repo is at a known revision. Pin it explicitly if you want the
exact weights this was verified against:

```bash
  --revision 173b94239f7c38886b2747b8d4a5db771a7e1232
```

---

## CPU and GPU

CPU works fully and is the default. CUDA is used automatically when
`TRANSLATION_DEVICE=auto` and `torch.cuda.is_available()`, but is never
required. Set `TRANSLATION_DEVICE="cpu"` or `"cuda"` to force one.

Measured on this machine (6 threads, CPU, `num_beams=5`):

| Workload | Time |
|---|---|
| Cold load (tokenizer + model) | **0.56 s** |
| `wheat flour` | ~1 s |
| A normal explanation sentence | **~2.3 s** |
| A batch of 3 recommendation strings | ~4–5 s |
| A 43-word label sentence | **~7.5 s** |
| RSS after load / peak | 385 MB / ~1.2 GB |

Repeated text is free: an LRU cache of 512 entries per language means the
steady state — a handful of explanation templates repeating across scans —
costs no inference at all.

If per-scan latency matters more than the last few percent of quality, set
`TRANSLATION_NUM_BEAMS=1`. Greedy decoding is roughly **2× faster** (2.3 s →
2.5 s on the sentence above, 24.9 s → 7.5 s on the worst case without a KV
cache). The default of 5 matches the model card.

---

## Offline behaviour

Everything runs locally once the weights are on disk. `TRANSLATION_MODEL_DIR`
is used when it exists, and loading from a local directory passes
`local_files_only=True`, so no network call is made even speculatively.

Set `TRANSLATION_OFFLINE=true` to make it a hard guarantee: if the weights are
missing, translation surfaces a clear error and the scan degrades to English
rather than hanging on a download.

---

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `SCAN_TRANSLATION_ENABLED` | `true` | `false` skips translation entirely |
| `TRANSLATION_PROVIDER` | `indictrans2` | provider swap point |
| `TRANSLATION_MODEL` | `ai4bharat/indictrans2-en-indic-dist-200M` | Hub id, used only if the dir is absent |
| `TRANSLATION_MODEL_DIR` | `var/models/indictrans2-en-indic-dist-200M` | wins when it exists |
| `TRANSLATION_MODEL_CACHE_DIR` | `var/models/hf` | used only when loading from the Hub |
| `TRANSLATION_DEVICE` | `auto` | `auto` / `cpu` / `cuda` |
| `TRANSLATION_NUM_BEAMS` | `5` | `1` for ~2× faster decoding |
| `TRANSLATION_MAX_NEW_TOKENS` | `256` | model cap is 256 |
| `TRANSLATION_MAX_CONCURRENCY` | `1` | inference workers; 1 serialises decodes |
| `TRANSLATION_OFFLINE` | `false` | `true` forbids all network access |
| `TRANSLATE_TIMEOUT_SECONDS` | `30` | per-call budget; on expiry the scan degrades to English |

**No Google credential is needed for translation.** `GOOGLE_APPLICATION_CREDENTIALS`
remains for OCR (Vision) only; `GOOGLE_CLOUD_PROJECT` is no longer read at all.

---

## How to test translation

The default suite is fast, offline and model-free — model-dependent tests are
opt-in, because nobody should download 1.1 GB to run `pytest`.

```bash
# Default: model tests are skipped
./venv/Scripts/python.exe -m pytest

# Real Hindi and Marathi, through the real client and the real scan pipeline
RUN_TRANSLATION_MODEL_TESTS=1 ./venv/Scripts/python.exe -m pytest \
    -m translation_model
```

On Windows, prefix `PYTHONIOENCODING=utf-8` if you want to *see* Devanagari in
the console; the default cp1252 console raises `UnicodeEncodeError` printing
it, which looks like a crash and is not one.

Quick manual check:

```bash
./venv/Scripts/python.exe -c "
from app.integrations.translate_client import translate_text
for lang in ('hi', 'mr'):
    r = translate_text('Palm oil is high in saturated fat.', lang)
    print(lang, r.translated, r.text)
"
```

---

## Changing the translation model

The provider is a registry entry, the same pattern as `OCR_PROVIDER` and
`CV_PROVIDER`:

- **Another IndicTrans2 checkpoint** (e.g. the 1B, or a RoPE long-context
  variant): point `TRANSLATION_MODEL` / `TRANSLATION_MODEL_DIR` at it. If its
  language tags differ, extend `APP_TO_TAG` in `app/integrations/indic_text.py`.
- **A different engine entirely** (CTranslate2, ONNX): add a function to
  `_PROVIDERS` in `app/integrations/translate_client.py` with the signature
  `(texts: list[str], target_language: str) -> list[str]` and select it via
  `TRANSLATION_PROVIDER`. Nothing else changes — the cache, batching, fallback
  policy and API contract all live above that seam.
- **Language pairs beyond Hindi/Marathi**: add the app code → FLORES tag pair
  to `APP_TO_TAG`, add the code to `SUPPORTED_LANGUAGES` in `config.py`, and
  make sure the frontend offers it.

### Do not bump `transformers`

`transformers` is pinned to `==4.51.3` for a reason that does not show up
until the first translation, and cannot be caught by the default test suite.

The model's own modelling code reads `past_key_values[0][0].shape[2]` — it
expects the **legacy tuple** key/value cache. Newer transformers hand it a
`Cache` object, and every translation dies with:

```
AttributeError: 'NoneType' object has no attribute 'shape'
```

Measured, one probe per version:

| `transformers` | `use_cache=True` |
|---|---|
| 4.38.2 | works |
| 4.44.2 | not installable — wants a `tokenizers` with no wheel; pip falls back to compiling Rust |
| 4.49.0 | works |
| **4.51.3** | **works — newest working, hence the pin** |
| 4.55.4 | fails — `KeyError: 'Cache only has 0 layers...'` |
| 4.56.2, 4.57.x | fails — the `AttributeError` above |

If you must move, run `RUN_TRANSLATION_MODEL_TESTS=1 pytest -m translation_model`
before and after. The runtime also re-probes this at load time
(`IndicTrans2Runtime._probe_use_cache`) and falls back to `use_cache=False`
rather than failing scans, but that path is ~2–3× slower — worth having as a
safety net, not worth relying on.

---

## Design notes

**No entity masking.** Numbers are *detected*, not hidden. See
`indic_text.digits_preserved`. The plan originally called for masking numbers
behind sentinel tokens; measurement showed the model already preserves digits
unmasked, and that two of three plausible sentinel schemes were corrupted
(`⟦0⟧` had its brackets stripped, silently turning a placeholder into a real
number). Masking would have invented a worse failure than the one it
prevented, so it was removed.

**Sentence splitting.** The model's source cap is 256 tokens and the tokenizer
is called with `truncation=True`, so an unsplit long label would silently lose
its tail. `indic_text.split_sentences` splits on `।?!` and on full stops that
are not decimals or abbreviations, then splits over-budget segments at clause
boundaries.

**Blanks never reach the model**, and neither does English — translating the
source language to itself is a multi-second no-op.

---

## Attribution

Model: **IndicTrans2** — AI4Bharat, IIT Madras.

> Gala, Jay; Chitale, Pranjal A; Raghavan, A K; Gumma, Varun; Doddapaneni,
> Sumanth; Kumar M, Aswanth; Nawale, Janki Atul; Sujatha, Anupama; Puduppully,
> Ratish; Raghavan, Vivek; Kumar, Pratyush; Khapra, Mitesh M; Dabre, Raj;
> Kunchukuttan, Anoop. *IndicTrans2: Towards High-Quality and Accessible
> Machine Translation Models for all 22 Scheduled Indian Languages.*
> Transactions on Machine Learning Research, 2023.
> <https://openreview.net/forum?id=vfT4YuzAYA>

Licensed **MIT**. The licence text ships with the weights at
`var/models/indictrans2-en-indic-dist-200M/LICENSE` and is redistributed
unmodified; this project's own licence is unaffected.

The language tags (`eng_Latn`, `hin_Deva`, `mar_Deva`) are FLORES-200 codes,
and the tokenizer's tag list is reproduced in `indic_text.LANGUAGE_TAGS`.
