"""Tests for the evaluator module."""
from __future__ import annotations

import pytest

from scraper import SEED_BUGS, ArduinoBug
from models import ModelResponse, MockModel
from evaluator import (
    EvalResult,
    evaluate,
    score_compilability,
    score_correctness,
    score_verbosity,
    extract_code_blocks,
    _heuristic_compilable,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _response(text: str, model_name: str = "test") -> ModelResponse:
    return ModelResponse(model_name=model_name, raw_text=text)


def _error_response() -> ModelResponse:
    return ModelResponse(model_name="test", raw_text="", error="API error")


I2C_BUG = next(b for b in SEED_BUGS if b.category == "i2c")
MEM_BUG = next(b for b in SEED_BUGS if b.category == "memory")
PERI_BUG = next(b for b in SEED_BUGS if b.category == "peripheral")


# ── extract_code_blocks ────────────────────────────────────────────────────────

class TestExtractCodeBlocks:
    def test_cpp_fence(self):
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


# ── score_compilability ────────────────────────────────────────────────────────

class TestCompilability:
    def test_error_response_scores_zero(self):
        assert score_compilability(_error_response()) == 0.0

    def test_empty_response_scores_zero(self):
        assert score_compilability(_response("")) == 0.0

    def test_no_code_block_scores_low(self):
        score = score_compilability(_response("Just prose, no code."))
        assert score <= 0.2

    def test_good_arduino_code_scores_high(self):
        text = """\
Here is the fix:

```cpp
#include <Wire.h>

void setup() {
  Wire.begin();
  Serial.begin(9600);
}

void loop() {
  Wire.beginTransmission(0x20);
  Wire.write(0x00);
  Wire.endTransmission(true);
  delay(100);
}
```
"""
        score = score_compilability(_response(text))
        assert score >= 0.5

    def test_placeholder_code_scores_lower(self):
        text = """\
```cpp
void setup() {
  // TODO: add setup code
  // ... rest of sketch
}
void loop() {}
```
"""
        score = score_compilability(_response(text))
        good_text = """\
```cpp
#include <Wire.h>
void setup() { Wire.begin(); }
void loop() {}
```
"""
        good_score = score_compilability(_response(good_text))
        assert score <= good_score


# ── _heuristic_compilable ──────────────────────────────────────────────────────

class TestHeuristicCompilable:
    def test_empty_returns_zero(self):
        assert _heuristic_compilable("") == 0.0

    def test_todo_penalised(self):
        code = "void setup() { /* TODO */ }\nvoid loop() {}"
        score = _heuristic_compilable(code)
        assert score < 0.7

    def test_good_sketch_scores_above_half(self):
        code = "#include <Wire.h>\nvoid setup() { Wire.begin(); }\nvoid loop() {}"
        assert _heuristic_compilable(code) > 0.5

    def test_score_in_range(self):
        for text in ["", "void setup(){}", "TODO ...", "#include <SPI.h>\nvoid setup(){}\nvoid loop(){}"]:
            s = _heuristic_compilable(text)
            assert 0.0 <= s <= 1.0


# ── score_correctness ─────────────────────────────────────────────────────────

class TestCorrectness:
    def test_error_response_scores_zero(self):
        assert score_correctness(_error_response(), I2C_BUG) == 0.0

    def test_empty_response_scores_zero(self):
        assert score_correctness(_response(""), I2C_BUG) == 0.0

    def test_relevant_keywords_score_higher(self):
        good = _response("Wire.endTransmission sendStop SDA SCL pull-up bus recovery NACK ACK clock stretch")
        bad = _response("hello world no relevant content here")
        assert score_correctness(good, I2C_BUG) > score_correctness(bad, I2C_BUG)

    def test_memory_keywords(self):
        resp = _response("buffer overflow dtostrf stack heap sram bounds corrupt null terminat sizeof")
        score = score_correctness(resp, MEM_BUG)
        assert score > 0.5

    def test_unknown_category_uses_general(self):
        bug = ArduinoBug(title="x", body="y", url="u", category="unknown_cat")
        resp = _response("root cause fix code serial setup loop")
        score = score_correctness(resp, bug)
        assert score >= 0.0

    def test_score_bounded(self):
        resp = _response("Wire SDA SCL stop condition sendstop endtransmission pull-up bus recovery clock stretch wire.begin restart nack ack")
        score = score_correctness(resp, I2C_BUG)
        assert 0.0 <= score <= 1.0


# ── score_verbosity ───────────────────────────────────────────────────────────

class TestVerbosity:
    def test_error_response_scores_zero(self):
        assert score_verbosity(_error_response()) == 0.0

    def test_empty_scores_zero(self):
        assert score_verbosity(_response("")) == 0.0

    def test_code_block_adds_score(self):
        with_code = _response("Some text.\n```cpp\nvoid setup(){}\n```")
        without_code = _response("Some text.")
        assert score_verbosity(with_code) > score_verbosity(without_code)

    def test_long_response_scores_higher(self):
        short = _response("Fix the bug.")
        long_text = " ".join(["word"] * 300)
        long = _response(long_text)
        assert score_verbosity(long) >= score_verbosity(short)

    def test_score_bounded(self):
        resp = _response("## Root Cause\n1. First\n```cpp\nvoid setup(){}\nvoid loop(){}\n```\n" + "word " * 400)
        score = score_verbosity(resp)
        assert 0.0 <= score <= 1.0

    def test_debug_keywords_add_score(self):
        with_debug = _response("Use a scope to test and debug the signal. verify with oscilloscope probe.")
        without_debug = _response("Replace the resistor.")
        assert score_verbosity(with_debug) >= score_verbosity(without_debug)


# ── evaluate ──────────────────────────────────────────────────────────────────

class TestEvaluate:
    def _make_result(self, bug=None):
        if bug is None:
            bug = I2C_BUG
        nem = MockModel("nvidia/nemotron-test")
        gpt = MockModel("gpt-4.1-nano")
        nem_resp = nem.fix_bug(bug)
        gpt_resp = gpt.fix_bug(bug)
        return evaluate(bug, nem_resp, gpt_resp)

    def test_returns_eval_result(self):
        result = self._make_result()
        assert isinstance(result, EvalResult)

    def test_winner_is_valid(self):
        result = self._make_result()
        assert result.winner in ("nemotron", "gpt", "tie")

    def test_scores_are_floats(self):
        result = self._make_result()
        for attr in ("nemotron_compilable", "gpt_compilable",
                     "nemotron_correctness", "gpt_correctness",
                     "nemotron_verbosity", "gpt_verbosity",
                     "nemotron_total", "gpt_total"):
            val = getattr(result, attr)
            assert isinstance(val, float), f"{attr} should be float"

    def test_scores_bounded(self):
        result = self._make_result()
        for attr in ("nemotron_compilable", "gpt_compilable",
                     "nemotron_correctness", "gpt_correctness",
                     "nemotron_verbosity", "gpt_verbosity",
                     "nemotron_total", "gpt_total"):
            val = getattr(result, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} out of [0,1]"

    def test_to_dict_structure(self):
        result = self._make_result()
        d = result.to_dict()
        assert "title" in d
        assert "nemotron" in d
        assert "gpt" in d
        assert "winner" in d
        assert "compilable" in d["nemotron"]
        assert "total" in d["gpt"]

    def test_all_seed_bugs_evaluate(self):
        nem = MockModel("nvidia/nemotron-test")
        gpt = MockModel("gpt-4.1-nano")
        for bug in SEED_BUGS:
            result = evaluate(bug, nem.fix_bug(bug), gpt.fix_bug(bug))
            assert result.winner in ("nemotron", "gpt", "tie")

    def test_error_responses_handled(self):
        err_nem = ModelResponse(model_name="nem", raw_text="", error="API error")
        err_gpt = ModelResponse(model_name="gpt", raw_text="", error="API error")
        result = evaluate(I2C_BUG, err_nem, err_gpt)
        assert result.winner == "tie"
        assert result.nemotron_total == 0.0
        assert result.gpt_total == 0.0
