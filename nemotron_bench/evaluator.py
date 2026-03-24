"""
Evaluation engine.

Measures three dimensions for each model response:
  1. Compilability  — whether extracted C++ compiles via arduino-cli (or heuristic)
  2. Correctness    — keyword / semantic scoring against the bug category
  3. Verbosity      — word count, code block presence, structured answer quality
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from . import config
from .models import ModelResponse, extract_code_blocks
from .scraper import ArduinoBug

logger = logging.getLogger(__name__)

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    bug: ArduinoBug
    nemotron_response: ModelResponse
    gpt_response: ModelResponse

    nemotron_compilable: float = 0.0
    gpt_compilable: float = 0.0

    nemotron_correctness: float = 0.0
    gpt_correctness: float = 0.0

    nemotron_verbosity: float = 0.0
    gpt_verbosity: float = 0.0

    nemotron_total: float = 0.0
    gpt_total: float = 0.0

    winner: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.bug.title,
            "category": self.bug.category,
            "url": self.bug.url,
            "nemotron": {
                "response": self.nemotron_response.raw_text,
                "compilable": self.nemotron_compilable,
                "correctness": self.nemotron_correctness,
                "verbosity": self.nemotron_verbosity,
                "total": self.nemotron_total,
                "latency_ms": self.nemotron_response.latency_ms,
                "word_count": self.nemotron_response.word_count,
                "tokens": self.nemotron_response.completion_tokens,
                "error": self.nemotron_response.error,
            },
            "gpt": {
                "response": self.gpt_response.raw_text,
                "compilable": self.gpt_compilable,
                "correctness": self.gpt_correctness,
                "verbosity": self.gpt_verbosity,
                "total": self.gpt_total,
                "latency_ms": self.gpt_response.latency_ms,
                "word_count": self.gpt_response.word_count,
                "tokens": self.gpt_response.completion_tokens,
                "error": self.gpt_response.error,
            },
            "winner": self.winner,
        }


# ── Arduino CLI compilation ───────────────────────────────────────────────────

def _arduino_cli_available() -> bool:
    cli = config.ARDUINO_CLI_PATH
    return shutil.which(cli) is not None


def _compile_sketch(code: str) -> tuple[bool, str]:
    """
    Write code to a temp sketch and try to compile it.
    Returns (success, stderr).
    """
    cli = config.ARDUINO_CLI_PATH
    fqbn = config.ARDUINO_FQBN
    timeout = config.ARDUINO_COMPILE_TIMEOUT

    # Arduino CLI requires the sketch file to have the same name as its directory
    with tempfile.TemporaryDirectory() as tmpdir:
        sketch_name = "battle_sketch"
        sketch_dir = os.path.join(tmpdir, sketch_name)
        os.makedirs(sketch_dir)
        sketch_file = os.path.join(sketch_dir, f"{sketch_name}.ino")
        with open(sketch_file, "w") as fh:
            fh.write(code)

        try:
            result = subprocess.run(
                [cli, "compile", "--fqbn", fqbn, sketch_dir],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Compilation timed out"
        except FileNotFoundError:
            return False, f"arduino-cli not found at '{cli}'"
        except Exception as exc:
            return False, str(exc)


# ── Heuristic compilability scorer ───────────────────────────────────────────

# Patterns that strongly suggest uncompilable / pseudo-code
_BAD_PATTERNS = [
    re.compile(r"\.\.\.", re.MULTILINE),          # ellipsis placeholder
    re.compile(r"<your\s+\w+>", re.IGNORECASE),   # placeholder text
    re.compile(r"TODO", re.IGNORECASE),
    re.compile(r"\/\/ rest of sketch", re.IGNORECASE),
]

_GOOD_PATTERNS = [
    re.compile(r"void\s+setup\s*\(\s*\)"),
    re.compile(r"void\s+loop\s*\(\s*\)"),
    re.compile(r"#include\s*<\w+\.h>"),
    re.compile(r"\bSerial\b"),
    re.compile(r"\bWire\b|\bSPI\b|\bSD\b"),
]


def _heuristic_compilable(code: str) -> float:
    """Score 0.0–1.0 estimating compilability without arduino-cli."""
    if not code.strip():
        return 0.0
    bad_hits = sum(1 for p in _BAD_PATTERNS if p.search(code))
    good_hits = sum(1 for p in _GOOD_PATTERNS if p.search(code))
    score = 0.5 + (good_hits * 0.1) - (bad_hits * 0.2)
    return max(0.0, min(1.0, score))


def score_compilability(response: ModelResponse) -> float:
    """
    Return a 0–1 compilability score.

    Uses arduino-cli when available; falls back to heuristic scoring.
    """
    if response.error or not response.raw_text.strip():
        return 0.0

    blocks = extract_code_blocks(response.raw_text)
    if not blocks:
        # No code block at all
        return 0.1

    if _arduino_cli_available():
        results = []
        for block in blocks[:2]:  # try first two blocks
            ok, _ = _compile_sketch(block)
            results.append(1.0 if ok else 0.0)
        return max(results)
    else:
        # Heuristic
        return max(_heuristic_compilable(b) for b in blocks)


# ── Correctness scorer ────────────────────────────────────────────────────────

# Keywords that indicate a correct, useful answer per category
_CORRECTNESS_KEYWORDS: dict[str, list[str]] = {
    "i2c": [
        "stop condition", "sendstop", "endtransmission", "sda", "scl",
        "pull-up", "pullup", "bus recovery", "clock stretch", "wire.begin",
        "restart", "nack", "ack",
    ],
    "spi": [
        "spi", "mosi", "miso", "cs", "chip select", "spcr", "transfer",
        "clock polarity", "cpol", "cpha",
    ],
    "memory": [
        "buffer", "overflow", "dtostrf", "stack", "heap", "sizeof",
        "sram", "array", "bounds", "corrupt", "null terminat",
    ],
    "timer": [
        "timer", "tccr", "prescaler", "overflow", "isr", "millis",
        "micros", "pwm", "compare", "ocr",
    ],
    "interrupt": [
        "interrupt", "isr", "sei", "cli", "attachinterrupt", "timer",
        "irremote", "latency", "drift",
    ],
    "watchdog": [
        "wdt_reset", "wdt_enable", "watchdog", "wdto", "timeout",
        "reset loop", "eeprom", "delay",
    ],
    "peripheral": [
        "timer1", "timer2", "servo", "sd", "spi", "interrupt", "pwm",
        "tccr1", "conflict", "attach",
    ],
    "general": [
        "root cause", "fix", "code", "serial", "setup", "loop",
    ],
}


def score_correctness(response: ModelResponse, bug: ArduinoBug) -> float:
    """
    Keyword-weighted correctness score 0–1.
    Checks how many category-specific diagnostic terms appear.
    """
    if response.error or not response.raw_text.strip():
        return 0.0

    text_lower = response.raw_text.lower()
    cat = bug.category if bug.category in _CORRECTNESS_KEYWORDS else "general"
    keywords = _CORRECTNESS_KEYWORDS[cat]
    hits = sum(1 for kw in keywords if kw in text_lower)
    return min(1.0, hits / max(1, len(keywords) * 0.4))


# ── Verbosity / quality scorer ────────────────────────────────────────────────

def score_verbosity(response: ModelResponse) -> float:
    """
    Score the structural quality and information density (0–1).

    Rewards:
      - Presence of code blocks
      - Structured sections (##, numbered lists)
      - Reasonable length (not too short, not bloated)
    """
    if response.error or not response.raw_text.strip():
        return 0.0

    text = response.raw_text
    score = 0.0

    # Code block present
    if extract_code_blocks(text):
        score += 0.30

    # Has sections (## or numbered)
    if re.search(r"^#{1,3} ", text, re.MULTILINE):
        score += 0.20
    if re.search(r"^\d+\.", text, re.MULTILINE):
        score += 0.10

    # Word count in sweet spot (80–600 words)
    wc = response.word_count
    if wc >= 80:
        score += 0.15
    if wc >= 200:
        score += 0.15
    if wc > 800:
        score -= 0.10  # penalise excessive verbosity

    # Contains diagnostic/testing section
    if re.search(r"test|debug|scope|oscilloscope|probe|verify", text, re.IGNORECASE):
        score += 0.10

    return max(0.0, min(1.0, score))


# ── Aggregate scorer ──────────────────────────────────────────────────────────

# Weights for the three dimensions
_WEIGHTS = {
    "compilable": float(os.getenv("WEIGHT_COMPILABLE", "0.40")),
    "correctness": float(os.getenv("WEIGHT_CORRECTNESS", "0.40")),
    "verbosity": float(os.getenv("WEIGHT_VERBOSITY", "0.20")),
}


def evaluate(bug: ArduinoBug, nemotron: ModelResponse, gpt: ModelResponse) -> EvalResult:
    """Score both responses and return an EvalResult."""
    result = EvalResult(bug=bug, nemotron_response=nemotron, gpt_response=gpt)

    for attr, response in [("nemotron", nemotron), ("gpt", gpt)]:
        comp = score_compilability(response)
        corr = score_correctness(response, bug)
        verb = score_verbosity(response)
        total = (
            comp * _WEIGHTS["compilable"]
            + corr * _WEIGHTS["correctness"]
            + verb * _WEIGHTS["verbosity"]
        )
        setattr(result, f"{attr}_compilable", round(comp, 3))
        setattr(result, f"{attr}_correctness", round(corr, 3))
        setattr(result, f"{attr}_verbosity", round(verb, 3))
        setattr(result, f"{attr}_total", round(total, 3))

    # Determine winner
    n_total = result.nemotron_total
    g_total = result.gpt_total
    if abs(n_total - g_total) < 0.02:
        result.winner = "tie"
    elif n_total > g_total:
        result.winner = "nemotron"
    else:
        result.winner = "gpt"

    return result
