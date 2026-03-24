"""Tests for the scraper module."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from nemotron_bench.scraper import (
    ArduinoBug,
    SEED_BUGS,
    fetch_bugs,
    _classify,
    _extract_code,
)
from bs4 import BeautifulSoup


# ── ArduinoBug dataclass ──────────────────────────────────────────────────────

class TestArduinoBug:
    def test_defaults(self):
        bug = ArduinoBug(title="test", body="body", url="http://x")
        assert bug.category == "general"
        assert bug.code_snippet == ""
        assert bug.tags == []

    def test_fields_stored(self):
        bug = ArduinoBug(
            title="I2C hang",
            body="SDA stuck low",
            url="https://forum.arduino.cc/t/1234",
            category="i2c",
            code_snippet="Wire.begin();",
            tags=["i2c", "wire"],
        )
        assert bug.title == "I2C hang"
        assert bug.category == "i2c"
        assert "wire" in bug.tags


# ── Seed bugs ─────────────────────────────────────────────────────────────────

class TestSeedBugs:
    def test_seed_count(self):
        assert len(SEED_BUGS) >= 5

    def test_seed_categories_covered(self):
        cats = {b.category for b in SEED_BUGS}
        assert "i2c" in cats
        assert "memory" in cats
        assert "peripheral" in cats

    def test_seed_bugs_have_code(self):
        for bug in SEED_BUGS:
            assert bug.code_snippet.strip(), f"Seed bug '{bug.title}' has no code snippet"

    def test_seed_expected_behaviors(self):
        i2c_bug = next(b for b in SEED_BUGS if b.category == "i2c")
        assert i2c_bug.expected_nemotron_behavior, "I2C seed bug missing nemotron behavior"
        assert i2c_bug.expected_gpt_behavior, "I2C seed bug missing gpt behavior"

    def test_seed_urls_are_strings(self):
        for bug in SEED_BUGS:
            assert isinstance(bug.url, str) and bug.url


# ── Classifier ────────────────────────────────────────────────────────────────

class TestClassify:
    def test_i2c_detection(self):
        assert _classify("I2C Wire SDA SCL timing") == "i2c"

    def test_memory_detection(self):
        assert _classify("buffer overflow stack corruption heap") == "memory"

    def test_timer_detection(self):
        assert _classify("Timer1 millis PWM prescaler") == "timer"

    def test_watchdog_detection(self):
        assert _classify("watchdog wdt_enable reset loop") == "watchdog"

    def test_interrupt_detection(self):
        assert _classify("interrupt ISR attachInterrupt latency") == "interrupt"

    def test_general_fallback(self):
        result = _classify("LED blinking hello world")
        assert result == "general"


# ── Code extraction ───────────────────────────────────────────────────────────

class TestExtractCode:
    def test_cpp_block(self):
        html = "<pre><code>void setup() { Wire.begin(); }</code></pre>"
        soup = BeautifulSoup(html, "lxml")
        code = _extract_code(soup)
        assert "Wire.begin" in code

    def test_multiple_blocks_joined(self):
        html = "<code>int x = 1;</code> text <code>int y = 2;</code>"
        soup = BeautifulSoup(html, "lxml")
        code = _extract_code(soup)
        assert code != ""

    def test_no_code_returns_empty(self):
        soup = BeautifulSoup("<p>just text</p>", "lxml")
        code = _extract_code(soup)
        assert code == ""


# ── fetch_bugs fallback behaviour ────────────────────────────────────────────

class TestFetchBugs:
    def test_returns_requested_count_with_seeds(self):
        # Patch network to fail so we get seed bugs
        with patch("nemotron_bench.scraper._search_forum", return_value=[]):
            bugs = fetch_bugs(3)
        assert len(bugs) == 3

    def test_returns_correct_type(self):
        with patch("nemotron_bench.scraper._search_forum", return_value=[]):
            bugs = fetch_bugs(2)
        for bug in bugs:
            assert isinstance(bug, ArduinoBug)

    def test_cycles_seeds_when_count_exceeds_seeds(self):
        n_seeds = len(SEED_BUGS)
        with patch("nemotron_bench.scraper._search_forum", return_value=[]):
            bugs = fetch_bugs(n_seeds + 3)
        assert len(bugs) == n_seeds + 3

    def test_prepends_live_bugs(self):
        live = [ArduinoBug(title="live", body="b", url="http://live")]
        with patch("nemotron_bench.scraper._search_forum", return_value=live):
            bugs = fetch_bugs(2)
        assert bugs[0].url == "http://live"
