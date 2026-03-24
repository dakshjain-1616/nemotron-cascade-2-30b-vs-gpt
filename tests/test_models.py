"""Tests for the models module — covers mock model and response dataclass."""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from scraper import SEED_BUGS, ArduinoBug
from models import (
    ModelResponse,
    MockModel,
    NemotronModel,
    GPTNanoModel,
    get_models,
    extract_code_blocks,
    _MOCK_RESPONSES,
)


# ── ModelResponse ──────────────────────────────────────────────────────────────

class TestModelResponse:
    def test_word_count(self):
        r = ModelResponse(model_name="test", raw_text="hello world foo bar")
        assert r.word_count == 4

    def test_char_count(self):
        r = ModelResponse(model_name="test", raw_text="abcde")
        assert r.char_count == 5

    def test_empty_response(self):
        r = ModelResponse(model_name="test", raw_text="")
        assert r.word_count == 0
        assert r.char_count == 0


# ── extract_code_blocks ────────────────────────────────────────────────────────

class TestExtractCodeBlocks:
    def test_fenced_cpp(self):
        text = "Here is the fix:\n```cpp\nvoid setup() {}\n```\nDone."
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "void setup" in blocks[0]

    def test_plain_fence(self):
        text = "```\nint x = 1;\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1

    def test_multiple_blocks(self):
        text = "```cpp\nint a;\n```\nText\n```cpp\nint b;\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2

    def test_no_blocks(self):
        blocks = extract_code_blocks("No code here at all.")
        assert blocks == []

    def test_arduino_fence(self):
        text = "```arduino\nvoid loop() {}\n```"
        blocks = extract_code_blocks(text)
        assert "void loop" in blocks[0]


# ── MockModel ─────────────────────────────────────────────────────────────────

class TestMockModel:
    def setup_method(self):
        self.nemotron = MockModel("nvidia/nemotron-test")
        self.gpt = MockModel("gpt-4.1-nano")

    def test_nemotron_returns_response(self):
        bug = SEED_BUGS[0]  # I2C bug
        resp = self.nemotron.fix_bug(bug)
        assert isinstance(resp, ModelResponse)
        assert resp.raw_text.strip() != ""

    def test_gpt_returns_response(self):
        bug = SEED_BUGS[0]
        resp = self.gpt.fix_bug(bug)
        assert isinstance(resp, ModelResponse)
        assert resp.raw_text.strip() != ""

    # ── Test spec: I2C timing bug ──────────────────────────────────────────────
    def test_i2c_nemotron_suggests_scope_traces(self):
        """Nemotron should suggest oscilloscope / scope traces for I2C bug."""
        i2c_bug = next(b for b in SEED_BUGS if b.category == "i2c")
        resp = self.nemotron.fix_bug(i2c_bug)
        lower = resp.raw_text.lower()
        assert any(kw in lower for kw in ["oscilloscope", "scope", "logic analys", "waveform"]), (
            f"Nemotron I2C response should mention scope traces: {resp.raw_text[:200]}"
        )

    def test_i2c_gpt_gives_concise_fix(self):
        """GPT-Nano should give a concise fix for I2C bug (shorter than Nemotron)."""
        i2c_bug = next(b for b in SEED_BUGS if b.category == "i2c")
        nem_resp = self.nemotron.fix_bug(i2c_bug)
        gpt_resp = self.gpt.fix_bug(i2c_bug)
        assert gpt_resp.word_count < nem_resp.word_count, (
            "GPT-Nano should be more concise than Nemotron on I2C bug"
        )

    # ── Test spec: Memory corruption ──────────────────────────────────────────
    def test_memory_both_detect_overflow(self):
        """Both models should detect the buffer overflow in memory bug."""
        mem_bug = next(b for b in SEED_BUGS if b.category == "memory")
        nem_resp = self.nemotron.fix_bug(mem_bug)
        gpt_resp = self.gpt.fix_bug(mem_bug)
        for resp in (nem_resp, gpt_resp):
            lower = resp.raw_text.lower()
            assert any(kw in lower for kw in ["overflow", "buffer", "corrupt", "sram", "bounds"]), (
                f"Model should detect overflow. Got: {resp.raw_text[:200]}"
            )

    def test_memory_gpt_explains_fix(self):
        """GPT-Nano should explain the fix for the memory corruption bug."""
        mem_bug = next(b for b in SEED_BUGS if b.category == "memory")
        resp = self.gpt.fix_bug(mem_bug)
        lower = resp.raw_text.lower()
        assert any(kw in lower for kw in ["fix", "increase", "size", "width", "char", "buf"]), (
            f"GPT-Nano should explain fix. Got: {resp.raw_text[:200]}"
        )

    # ── Test spec: Peripheral conflict ────────────────────────────────────────
    def test_peripheral_nemotron_catches_register_clash(self):
        """Nemotron's larger context should catch timer/register conflicts."""
        peri_bug = next(b for b in SEED_BUGS if b.category == "peripheral")
        resp = self.nemotron.fix_bug(peri_bug)
        lower = resp.raw_text.lower()
        assert any(kw in lower for kw in ["timer1", "timer2", "tccr", "register", "interrupt"]), (
            f"Nemotron should identify register/timer clash. Got: {resp.raw_text[:200]}"
        )

    def test_peripheral_gpt_recommends_alternative(self):
        """GPT-Nano should recommend a fix for the peripheral conflict."""
        peri_bug = next(b for b in SEED_BUGS if b.category == "peripheral")
        resp = self.gpt.fix_bug(peri_bug)
        lower = resp.raw_text.lower()
        assert any(kw in lower for kw in ["timer2", "servotime", "alternative", "recommend", "avoid"]), (
            f"GPT-Nano should recommend alternative. Got: {resp.raw_text[:200]}"
        )

    def test_mock_response_has_latency(self):
        resp = self.nemotron.fix_bug(SEED_BUGS[0])
        assert resp.latency_ms > 0

    def test_mock_response_has_token_counts(self):
        resp = self.gpt.fix_bug(SEED_BUGS[0])
        assert resp.prompt_tokens > 0
        assert resp.completion_tokens > 0

    def test_all_categories_covered(self):
        from scraper import SEED_BUGS as _seeds
        categories = {b.category for b in _seeds}
        for cat in categories:
            assert cat in _MOCK_RESPONSES or "general" in _MOCK_RESPONSES

    def test_watchdog_bug_response(self):
        wdt_bug = next(b for b in SEED_BUGS if b.category == "watchdog")
        resp = self.nemotron.fix_bug(wdt_bug)
        lower = resp.raw_text.lower()
        assert any(kw in lower for kw in ["wdt", "watchdog", "reset", "timeout", "eeprom"])

    def test_interrupt_bug_response(self):
        irq_bug = next(b for b in SEED_BUGS if b.category == "interrupt")
        resp = self.gpt.fix_bug(irq_bug)
        lower = resp.raw_text.lower()
        assert any(kw in lower for kw in ["timer", "irremote", "drift", "millis", "interrupt"])


# ── get_models ────────────────────────────────────────────────────────────────

class TestGetModels:
    def test_force_mock_returns_mock_models(self):
        nemotron, gpt = get_models(force_mock=True)
        assert isinstance(nemotron, MockModel)
        assert isinstance(gpt, MockModel)

    def test_no_keys_returns_mock(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "", "OPENAI_API_KEY": "", "OPENROUTER_API_KEY": ""}):
            # Need to reload config after patching
            import importlib
            import config as cfg
            importlib.reload(cfg)
            nem, gpt = get_models(force_mock=False)
            # With empty keys, config.mock_mode() returns True
            assert isinstance(nem, MockModel)

    def test_live_models_created_with_keys(self):
        with patch.dict(os.environ, {
            "NVIDIA_API_KEY": "nvapi-realkey123",
            "OPENAI_API_KEY": "sk-realkey456",
        }):
            import importlib
            import config as cfg
            importlib.reload(cfg)
            from models import NemotronModel, GPTNanoModel
            # Just verify we can instantiate them
            nem = NemotronModel()
            gpt = GPTNanoModel()
            assert isinstance(nem, NemotronModel)
            assert isinstance(gpt, GPTNanoModel)
