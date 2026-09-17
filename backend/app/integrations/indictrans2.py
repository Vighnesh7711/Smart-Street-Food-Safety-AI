"""Local IndicTrans2 runtime: model lifecycle and CPU inference.

Replaces the Google Cloud Translation call with an in-process model. Nothing
leaves the machine; there is no API key, no quota, and no bill.

WHY `transformers` IS PINNED TO 4.51.3
--------------------------------------
The model's own modelling code does `past_key_values[0][0].shape[2]` -- it
expects the *legacy tuple* key/value cache. Newer transformers hand it a
`Cache` object and it dies with `AttributeError: 'NoneType' object has no
attribute 'shape'` on the first `generate()`.

Measured, in a scratch venv, one probe per version:

    4.38.2  ok        4.51.3  ok   <- newest working, hence the pin
    4.44.2  no cp314-compatible tokenizers; pip falls back to compiling Rust
    4.55.4  KeyError: 'Cache only has 0 layers, attempted to access layer...'
    4.56.2+ AttributeError: 'NoneType' object has no attribute 'shape'

The cache is worth having: it is 2.2x on a normal sentence and 3.3x on a long
one, which is the difference between 7.5s and 24.9s on a 43-word label.

`_probe_use_cache` below re-checks that assumption at load time rather than
trusting it, because the failure is a hard crash on the first translation --
not an import error, and not something a test suite would catch without the
model present.

WHY THERE IS NO ASYNC CODE HERE
-------------------------------
`translate_many` is called from sync endpoint functions, which FastAPI already
runs in a threadpool -- the event loop is not at risk. Inference is dispatched
to a single-worker executor, which serialises decodes so concurrent scans
queue instead of starting N CPU-bound generations and thrashing the box.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from typing import List, Optional, Sequence

from app.integrations import indic_text

logger = logging.getLogger(__name__)


class TranslationRuntimeError(RuntimeError):
    """Base class, so callers can catch one thing.

    `translate_client` treats every one of these as "degrade to English" --
    the scan must still succeed. The distinction between them exists for logs
    and diagnostics, not for control flow.
    """


class ModelDownloadError(TranslationRuntimeError):
    """Weights are not on disk and could not be fetched."""


class ModelInitializationError(TranslationRuntimeError):
    """Weights are present but the tokenizer or model would not load."""


class ModelInferenceError(TranslationRuntimeError):
    """The model loaded but generating a translation failed."""


class TranslationTimeout(TranslationRuntimeError):
    """Inference did not finish inside the configured budget."""


class IndicTrans2Runtime:
    """Owns one tokenizer + one model, loaded once and reused forever."""

    def __init__(
        self,
        *,
        model_id: str,
        model_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        device: str = "auto",
        num_beams: int = 5,
        max_new_tokens: int = 256,
        timeout_seconds: float = 30.0,
        max_concurrency: int = 1,
        offline: bool = False,
    ):
        self.model_id = model_id
        self.model_dir = model_dir
        self.cache_dir = cache_dir
        self._requested_device = device
        self.num_beams = num_beams
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds = timeout_seconds
        self.offline = offline

        self._tokenizer = None
        self._model = None
        self._torch = None
        self._device = None
        self._use_cache = True

        # Guards the load. FastAPI runs sync endpoints in a threadpool, so two
        # scans really can arrive together, and without this both would build
        # a model -- 400 MB of weights and a second copy of torch's caches.
        self._load_lock = threading.Lock()

        # one worker => inference is serialised, so a burst of scans queues.
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_concurrency),
            thread_name_prefix="indictrans2",
        )

    # --- lifecycle -------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> Optional[str]:
        return self._device

    @property
    def use_cache(self) -> bool:
        """Whether the KV cache survived the load-time probe."""
        return self._use_cache

    def _resolve_source(self) -> str:
        """Prefer the local directory, so a downloaded model works offline.

        Falls back to the Hub id so a fresh clone can fetch on first use,
        which is the documented one-time setup.
        """
        if self.model_dir is not None and Path(self.model_dir).is_dir():
            return str(self.model_dir)
        if self.offline:
            raise ModelDownloadError(
                f"TRANSLATION_OFFLINE is set but no model was found at "
                f"{self.model_dir!r}. Download it once, or unset "
                f"TRANSLATION_OFFLINE."
            )
        return self.model_id

    def _pick_device(self, torch) -> str:
        if self._requested_device and self._requested_device != "auto":
            return self._requested_device
        # CUDA is used when present, never required -- CPU is fully supported.
        return "cuda" if torch.cuda.is_available() else "cpu"

    def load(self) -> None:
        """Load the tokenizer and model. Idempotent and thread-safe."""
        if self._model is not None:
            return

        with self._load_lock:
            # Re-check inside the lock: another thread may have won the race
            # while we waited for it.
            if self._model is not None:
                return

            try:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            except ImportError as exc:  # pragma: no cover - env problem
                raise ModelInitializationError(
                    f"torch/transformers are not installed: {exc}. "
                    f"pip install -r requirements.txt"
                ) from exc

            source = self._resolve_source()
            # A local directory needs no network at all; local_files_only
            # makes that a guarantee rather than an expectation.
            local_only = Path(source).is_dir()
            device = self._pick_device(torch)

            logger.info("Loading IndicTrans2 translation model from %s...", source)

            kwargs = {"trust_remote_code": True}
            if local_only:
                kwargs["local_files_only"] = True
            if self.cache_dir is not None and not local_only:
                kwargs["cache_dir"] = str(self.cache_dir)

            try:
                tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
                model = AutoModelForSeq2SeqLM.from_pretrained(source, **kwargs)
            except OSError as exc:
                # Missing files, offline cache miss, a gated repo we cannot
                # read -- all "we do not have the weights".
                raise ModelDownloadError(
                    f"Could not load the translation model from {source!r}: {exc}"
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise ModelInitializationError(
                    f"Translation model failed to initialize: {exc}"
                ) from exc

            # float32 on CPU. The model card suggests float16, which is GPU
            # guidance: on CPU it is slower and unsupported for some ops.
            model.eval()
            model.to(device)

            self._torch = torch
            self._tokenizer = tokenizer
            self._model = model
            self._device = device

            logger.info(
                "IndicTrans2 model loaded on %s (torch %s, transformers %s)",
                device,
                torch.__version__,
                _transformers_version(),
            )

            self._use_cache = self._probe_use_cache()

    def _probe_use_cache(self) -> bool:
        """Verify the KV cache works on this transformers build.

        Cheap (a 1-token decode) and it doubles as a warmup. If the remote
        code's legacy-tuple expectation is not met, every translate would
        crash, so we find out here and fall back to the slow-but-correct
        path instead of failing scans.
        """
        try:
            self._generate(["eng_Latn hin_Deva ok"], use_cache=True)
        except Exception as exc:  # noqa: BLE001 - any failure means "no cache"
            logger.warning(
                "IndicTrans2 KV cache is unusable with transformers %s (%s: %s). "
                "Falling back to use_cache=False; translations will be slower. "
                "The supported pin is transformers==4.51.3.",
                _transformers_version(),
                type(exc).__name__,
                exc,
            )
            return False
        return True

    # --- inference -------------------------------------------------------

    def _generate(self, segments: Sequence[str], *, use_cache: bool) -> List[str]:
        torch = self._torch
        tokenizer = self._tokenizer
        model = self._model

        encoded = tokenizer(
            list(segments),
            truncation=True,
            padding="longest",
            return_tensors="pt",
            return_attention_mask=True,
        ).to(self._device)

        with torch.no_grad():
            generated = model.generate(
                **encoded,
                use_cache=use_cache,
                min_length=0,
                max_length=self.max_new_tokens,
                num_beams=self.num_beams,
                num_return_sequences=1,
            )

        return tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

    def _translate_now(
        self, segments: Sequence[str], owners: Sequence[int], texts: Sequence[str]
    ) -> List[str]:
        """One decode for every segment, regrouped back into per-text results.

        Batching at the segment level rather than the text level is what keeps
        an explanation plus its recommendations to a single `generate()` call
        even when the explanation splits into several sentences.
        """
        decoded = self._generate(segments, use_cache=self._use_cache)

        grouped: dict = {}
        for owner, piece in zip(owners, decoded):
            grouped.setdefault(owner, []).append(piece)

        results = list(texts)
        for index, pieces in grouped.items():
            translated = indic_text.postprocess(pieces)
            if not indic_text.digits_preserved(texts[index], translated):
                # A detector, not a guard: we never rewrite the text. Numbers
                # on a food label are the one thing a plausible-looking
                # translation must not quietly change. See indic_text for why
                # masking numbers was tried and abandoned.
                logger.warning(
                    "Translation altered the numbers in a label: %r -> %r",
                    texts[index],
                    translated,
                )
            results[index] = translated
        return results

    def _run_bounded(self, job):
        """Run `job` on the inference worker, bounded by the timeout.

        The worker is deliberate even with one thread: it bounds how long the
        caller waits. Note Python cannot cancel a running thread, so on
        timeout the caller returns immediately but that one decode finishes in
        the background. With `max_new_tokens` capped and the queue serialised
        the outstanding work is bounded, and a process pool would not be worth
        its cost here.
        """
        future = self._executor.submit(job)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            raise TranslationTimeout(
                f"Translation exceeded {self.timeout_seconds:g}s"
            ) from exc

    def translate_batch(self, texts: Sequence[str], target_tag: str) -> List[str]:
        """Translate several English strings into `target_tag`.

        Returns one result per input, in order. Blank inputs come back
        unchanged rather than being sent to the model.

        Raises a `TranslationRuntimeError` subclass on any failure; callers
        degrade to English rather than propagating.
        """
        if not texts:
            return []

        self.load()

        segments: List[str] = []
        owners: List[int] = []
        for index, text in enumerate(texts):
            for segment in indic_text.preprocess(text, target_tag):
                segments.append(segment)
                owners.append(index)

        # Nothing translatable (all inputs blank) -- no model call at all.
        if not segments:
            return list(texts)

        def job() -> List[str]:
            try:
                return self._translate_now(segments, owners, texts)
            except TranslationRuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001 - never escape raw
                raise ModelInferenceError(
                    f"Translation inference failed: {exc}"
                ) from exc

        return self._run_bounded(job)

    def translate(self, text: str, target_tag: str) -> str:
        """Translate one English string. See `translate_batch`."""
        return self.translate_batch([text], target_tag)[0]

    def warmup(self) -> None:
        """Load eagerly. Optional -- `translate` loads lazily anyway."""
        self.load()

    def shutdown(self) -> None:
        """Release the executor. Used by tests; the app lives until exit."""
        self._executor.shutdown(wait=False)


def _transformers_version() -> str:
    """Best-effort version string for diagnostics."""
    try:
        from transformers import __version__

        return __version__
    except Exception:  # noqa: BLE001 - diagnostics must never raise
        return "unknown"
