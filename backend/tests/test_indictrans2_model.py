"""Real IndicTrans2 inference, through the real translate_client.

OPT-IN. These load ~1.1 GB of weights and take seconds per inference, so they
are skipped unless you ask for them:

    RUN_TRANSLATION_MODEL_TESTS=1 pytest tests/test_indictrans2_model.py

They are skipped rather than run-and-slow because the default suite must stay
fast and offline -- and because a fresh clone has no weights at all.

What is deliberately NOT asserted: exact translation strings. The model is
free to improve or be replaced, and pinning "wheat flour" to one particular
Devanagari rendering would turn a model upgrade into a test failure. What we
assert is that the output is real: the right script, the right length, the
numbers intact, and Marathi not silently returning Hindi.
"""

import os

import pytest

from app.integrations import translate_client
from app.integrations.translate_client import translate_many, translate_text

pytestmark = [
    pytest.mark.translation_model,
    pytest.mark.skipif(
        os.environ.get("RUN_TRANSLATION_MODEL_TESTS") != "1",
        reason="opt-in: set RUN_TRANSLATION_MODEL_TESTS=1 (loads ~1.1 GB of weights)",
    ),
]

# Devanagari block. Hindi and Marathi both use it, so this proves "real Indic
# output" but not *which* language -- the Marathi-vs-Hindi test below does.
DEVANAGARI = range(0x0900, 0x0980)

EXPLANATION = "Palm oil is high in saturated fat and may increase the risk of heart disease."
WITH_NUMBERS = "This product contains 32 percent saturated fat and 500 mg of sodium."


@pytest.fixture(scope="module", autouse=True)
def _enable_translation():
    """conftest sets SCAN_TRANSLATION_ENABLED=false suite-wide so an ordinary
    run never reaches a provider. This module exists to reach the real one, so
    it has to turn translation back on -- without this, every assertion below
    passes against un-translated English."""
    previous = translate_client.settings.SCAN_TRANSLATION_ENABLED
    translate_client.settings.SCAN_TRANSLATION_ENABLED = True
    yield
    translate_client.settings.SCAN_TRANSLATION_ENABLED = previous


@pytest.fixture(scope="module", autouse=True)
def _warm_model():
    """Load once per module: a cold load per test would dominate the runtime."""
    translate_client.get_runtime().warmup()
    yield
    translate_client.clear_cache()


@pytest.fixture(autouse=True)
def _clear_cache():
    translate_client.clear_cache()
    yield
    translate_client.clear_cache()


def _has_devanagari(text: str) -> bool:
    return any(ord(char) in DEVANAGARI for char in text)


class TestEnglishIsUntouched:
    def test_english_never_reaches_the_model(self, monkeypatch):
        """English is the source language; translating it to itself would be a
        pointless multi-second inference."""

        def _explode(*args, **kwargs):
            raise AssertionError("English must not hit the model")

        monkeypatch.setattr(translate_client, "_run_provider", _explode)
        result = translate_text(EXPLANATION, "en")

        assert result.text == EXPLANATION
        assert result.translated is False
        assert result.warning is None


class TestHindi:
    def test_short_input(self):
        result = translate_text("wheat flour", "hi")

        assert result.translated is True
        assert result.warning is None
        assert _has_devanagari(result.text), result.text

    def test_realistic_explanation(self):
        result = translate_text(EXPLANATION, "hi")

        assert result.translated is True
        assert _has_devanagari(result.text), result.text
        # A one-line English sentence must not come back as a novel.
        assert len(result.text) < len(EXPLANATION) * 4


class TestMarathi:
    def test_short_input(self):
        result = translate_text("wheat flour", "mr")

        assert result.translated is True
        assert _has_devanagari(result.text), result.text

    def test_marathi_is_not_silently_hindi(self):
        """A wrong tag would return Hindi for Marathi and look fine, because
        both are Devanagari. This is the only check that catches it."""
        hindi = translate_text(EXPLANATION, "hi").text
        marathi = translate_text(EXPLANATION, "mr").text

        assert marathi != hindi

    def test_cached_per_language(self):
        """The cache is keyed by language, so the two must not collide."""
        hindi = translate_text("Check the label.", "hi").text
        marathi = translate_text("Check the label.", "mr").text

        assert hindi != marathi


class TestNumbers:
    def test_numbers_survive_a_real_translation(self):
        """The measured claim from the spike, pinned so a model change that
        starts mangling quantities is caught. See indic_text for why we detect
        rather than mask.

        Asserts the text was actually translated *as well as* carrying the
        numbers: an untranslated English passthrough contains "32" trivially,
        so a digits-only assertion would pass while nothing worked.
        """
        for language in ("hi", "mr"):
            result = translate_text(WITH_NUMBERS, language)
            assert result.translated is True, language
            assert _has_devanagari(result.text), f"{language}: {result.text}"
            assert "32" in result.text, f"{language}: lost 32 -> {result.text}"
            assert "500" in result.text, f"{language}: lost 500 -> {result.text}"


class TestBatching:
    def test_many_strings_return_in_order(self):
        texts = [
            "This product contains wheat flour.",
            "Reduce consumption if you have a gluten allergy.",
            "Check the expiry date before eating.",
        ]
        results = translate_many(texts, "hi")

        assert len(results) == len(texts)
        assert all(r.translated for r in results)
        assert all(_has_devanagari(r.text) for r in results)

    def test_results_are_not_duplicated_across_slots(self):
        """Guards the regroup step: a batching bug that mis-assigns segments
        would give two inputs the same translation."""
        results = translate_many(
            ["Wheat flour.", "Check the expiry date before eating."], "hi"
        )
        assert all(r.translated for r in results)
        assert results[0].text != results[1].text


class TestCaching:
    def test_second_call_does_not_re_infer(self, monkeypatch):
        runtime = translate_client.get_runtime()
        calls = []
        original = runtime.translate_batch

        def _counting(texts, tag):
            calls.append(list(texts))
            return original(texts, tag)

        monkeypatch.setattr(runtime, "translate_batch", _counting)

        first = translate_text(EXPLANATION, "hi")
        second = translate_text(EXPLANATION, "hi")

        assert len(calls) == 1, "the cache should absorb the second call"
        assert first.text == second.text


class TestDisabledAndUnsupported:
    def test_disabled_makes_no_model_call(self, monkeypatch):
        monkeypatch.setattr(
            translate_client.settings, "SCAN_TRANSLATION_ENABLED", False
        )

        def _explode(*args, **kwargs):
            raise AssertionError("disabled translation must not infer")

        monkeypatch.setattr(translate_client, "_run_provider", _explode)
        result = translate_text(EXPLANATION, "hi")

        assert result.translated is False
        assert result.warning is None

    def test_unsupported_language_degrades(self):
        result = translate_text(EXPLANATION, "ta")

        assert result.translated is False
        assert result.text == EXPLANATION
        assert result.warning is not None
