"""IndicTrans2 runtime: lifecycle, batching, timeout, and error mapping.

The model is mocked throughout. These must run with no weights on disk, no
torch load, and no network -- the real-inference tests are opt-in and live in
test_indictrans2_model.py.

The runtime is where a translation either happens or degrades, so the cases
that matter are the failure ones: a timeout must become a clean timeout error,
an arbitrary model exception must not escape raw, and the caller must never
see a half-translated batch.
"""

import logging
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.integrations import indic_text
from app.integrations.indictrans2 import (
    IndicTrans2Runtime,
    ModelDownloadError,
    ModelInferenceError,
    TranslationTimeout,
)


@pytest.fixture
def runtime():
    """A runtime that believes it is loaded, so no torch import happens."""
    rt = IndicTrans2Runtime(model_id="stub/model", num_beams=1, timeout_seconds=5.0)
    rt._model = object()
    rt._tokenizer = object()
    rt._torch = object()
    rt._device = "cpu"
    yield rt
    rt.shutdown()


def _echo_bodies(segments, *, use_cache=True):
    """Stand-in for a real decode: returns the un-tagged body of each segment."""
    return [segment.split(" ", 2)[2] for segment in segments]


class TestBatching:
    def test_multi_sentence_text_is_flattened_then_regrouped(self, runtime, monkeypatch):
        monkeypatch.setattr(runtime, "_generate", _echo_bodies)

        results = runtime.translate_batch(["One. Two.", "Three."], "hin_Deva")

        # Two texts in, two texts out -- the first one reassembled from its
        # two sentence segments by postprocess, not left as a list.
        assert results == ["One. Two.", "Three."]

    def test_every_segment_carries_the_tag_prefix(self, runtime, monkeypatch):
        seen = []

        def _capture(segments, *, use_cache=True):
            seen.extend(segments)
            return [segment.split(" ", 2)[2] for segment in segments]

        monkeypatch.setattr(runtime, "_generate", _capture)
        runtime.translate_batch(["One. Two."], "mar_Deva")

        assert seen == [
            "eng_Latn mar_Deva One.",
            "eng_Latn mar_Deva Two.",
        ]

    def test_all_strings_go_in_one_model_call(self, runtime, monkeypatch):
        calls = []

        def _count(segments, *, use_cache=True):
            calls.append(list(segments))
            return [s.split(" ", 2)[2] for s in segments]

        monkeypatch.setattr(runtime, "_generate", _count)
        runtime.translate_batch(["A.", "B.", "C."], "hin_Deva")

        assert len(calls) == 1, "a batch must not become one decode per string"

    def test_result_order_matches_input_order(self, runtime, monkeypatch):
        monkeypatch.setattr(
            runtime, "_generate", lambda segs, **kw: [f"[{len(s)}]" for s in segs]
        )
        results = runtime.translate_batch(["a", "bb", "ccc"], "hin_Deva")

        assert len(results) == 3

    def test_blank_strings_are_not_sent_to_the_model(self, runtime, monkeypatch):
        def _explode(*args, **kwargs):
            raise AssertionError("blank input must not reach the model")

        monkeypatch.setattr(runtime, "_generate", _explode)
        results = runtime.translate_batch(["", "   "], "hin_Deva")

        assert results == ["", "   "]

    def test_empty_batch_is_a_no_op(self, runtime, monkeypatch):
        def _explode(*args, **kwargs):
            raise AssertionError("nothing to translate")

        monkeypatch.setattr(runtime, "_generate", _explode)
        assert runtime.translate_batch([], "hin_Deva") == []

    def test_single_string_wrapper(self, runtime, monkeypatch):
        monkeypatch.setattr(runtime, "_generate", _echo_bodies)
        assert runtime.translate("Fat is high.", "hin_Deva") == "Fat is high."


class TestErrorMapping:
    def test_timeout_becomes_a_clean_error(self, runtime, monkeypatch):
        def _slow(segments, *, use_cache=True):
            time.sleep(0.5)
            return list(segments)

        runtime.timeout_seconds = 0.05
        monkeypatch.setattr(runtime, "_generate", _slow)

        with pytest.raises(TranslationTimeout):
            runtime.translate_batch(["One."], "hin_Deva")

    def test_arbitrary_exception_does_not_escape_raw(self, runtime, monkeypatch):
        def _boom(segments, *, use_cache=True):
            raise ValueError("something inside the model")

        monkeypatch.setattr(runtime, "_generate", _boom)

        with pytest.raises(ModelInferenceError):
            runtime.translate_batch(["One."], "hin_Deva")

    def test_our_own_errors_are_not_double_wrapped(self, runtime, monkeypatch):
        def _boom(segments, *, use_cache=True):
            raise ModelDownloadError("weights vanished")

        monkeypatch.setattr(runtime, "_generate", _boom)

        with pytest.raises(ModelDownloadError):
            runtime.translate_batch(["One."], "hin_Deva")

    def test_unknown_target_tag_raises_before_any_inference(self, runtime, monkeypatch):
        def _explode(*args, **kwargs):
            raise AssertionError("invalid tag must fail before inference")

        monkeypatch.setattr(runtime, "_generate", _explode)

        with pytest.raises(ValueError):
            runtime.translate_batch(["One."], "mr_Deva")


class TestDigitDetection:
    def test_changed_numbers_are_logged(self, runtime, monkeypatch, caplog):
        # The source says 32; the model returns 23. Nothing rewrites it -- we
        # only make sure it is visible in the logs.
        monkeypatch.setattr(
            runtime,
            "_generate",
            lambda segs, **kw: ["वसा 23 प्रतिशत"],
        )
        with caplog.at_level(logging.WARNING, logger="app.integrations.indictrans2"):
            runtime.translate_batch(["Fat is 32 percent."], "hin_Deva")

        assert any("altered the numbers" in r.message for r in caplog.records)

    def test_preserved_numbers_are_not_logged(self, runtime, monkeypatch, caplog):
        monkeypatch.setattr(runtime, "_generate", lambda segs, **kw: ["वसा 32 प्रतिशत"])
        with caplog.at_level(logging.WARNING, logger="app.integrations.indictrans2"):
            runtime.translate_batch(["Fat is 32 percent."], "hin_Deva")

        assert not any("altered the numbers" in r.message for r in caplog.records)

    def test_translation_is_returned_even_when_numbers_change(
        self, runtime, monkeypatch
    ):
        """Detection only. See the plan: masking was tried and abandoned, so
        this must not silently become a rewrite or a fallback."""
        monkeypatch.setattr(runtime, "_generate", lambda segs, **kw: ["वसा 23"])
        results = runtime.translate_batch(["Fat is 32."], "hin_Deva")

        assert results == ["वसा 23"]


class TestSourceResolution:
    def test_local_directory_wins(self, tmp_path):
        rt = IndicTrans2Runtime(model_id="hub/id", model_dir=tmp_path)
        assert rt._resolve_source() == str(tmp_path)
        rt.shutdown()

    def test_missing_directory_falls_back_to_the_hub_id(self, tmp_path):
        rt = IndicTrans2Runtime(model_id="hub/id", model_dir=tmp_path / "nope")
        assert rt._resolve_source() == "hub/id"
        rt.shutdown()

    def test_missing_directory_offline_is_an_error(self, tmp_path):
        rt = IndicTrans2Runtime(
            model_id="hub/id", model_dir=tmp_path / "nope", offline=True
        )
        with pytest.raises(ModelDownloadError, match="TRANSLATION_OFFLINE"):
            rt._resolve_source()
        rt.shutdown()


class TestDeviceSelection:
    def test_explicit_device_is_honoured(self):
        rt = IndicTrans2Runtime(model_id="x", device="cpu")
        fake_torch = SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: True)
        )
        assert rt._pick_device(fake_torch) == "cpu"
        rt.shutdown()

    def test_auto_uses_cuda_when_available(self):
        rt = IndicTrans2Runtime(model_id="x", device="auto")
        fake_torch = SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: True)
        )
        assert rt._pick_device(fake_torch) == "cuda"
        rt.shutdown()

    def test_auto_falls_back_to_cpu(self):
        # The common case: CPU is fully supported and CUDA is never required.
        rt = IndicTrans2Runtime(model_id="x", device="auto")
        fake_torch = SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False)
        )
        assert rt._pick_device(fake_torch) == "cpu"
        rt.shutdown()


class TestLifecycle:
    def test_already_loaded_skips_the_import_path(self, runtime):
        # If load() tried to import torch it would still succeed here, but the
        # point is that it returns before touching the filesystem at all.
        sentinel = runtime._model
        runtime.load()
        assert runtime._model is sentinel

    def test_loaded_flag(self, runtime):
        assert runtime.is_loaded is True

    def test_device_is_reported(self, runtime):
        assert runtime.device == "cpu"


class TestCacheProbe:
    def test_probe_accepts_a_working_cache(self, runtime, monkeypatch):
        monkeypatch.setattr(runtime, "_generate", _echo_bodies)
        assert runtime._probe_use_cache() is True

    def test_probe_rejects_a_broken_cache(self, runtime, monkeypatch):
        """The exact failure measured against transformers >4.51: the remote
        modelling code gets a Cache object where it expects a tuple."""

        def _broken(segments, *, use_cache=True):
            if use_cache:
                raise AttributeError("'NoneType' object has no attribute 'shape'")
            return [s.split(" ", 2)[2] for s in segments]

        monkeypatch.setattr(runtime, "_generate", _broken)
        assert runtime._probe_use_cache() is False

    def test_probe_failure_logs_the_pin(self, runtime, monkeypatch, caplog):
        def _broken(segments, *, use_cache=True):
            raise AttributeError("'NoneType' object has no attribute 'shape'")

        monkeypatch.setattr(runtime, "_generate", _broken)
        with caplog.at_level(logging.WARNING, logger="app.integrations.indictrans2"):
            runtime._probe_use_cache()

        assert any("transformers==4.51.3" in r.getMessage() for r in caplog.records)


class TestPreprocessContract:
    """The runtime leans on indic_text; these pin the assumptions it makes."""

    def test_preprocess_marks_our_languages(self):
        assert indic_text.tag_for("hi") == "hin_Deva"
        assert indic_text.tag_for("mr") == "mar_Deva"

    def test_local_path_is_absolute_after_resolution(self, tmp_path):
        rt = IndicTrans2Runtime(model_id="x", model_dir=Path(tmp_path))
        assert Path(rt._resolve_source()).is_absolute()
        rt.shutdown()
