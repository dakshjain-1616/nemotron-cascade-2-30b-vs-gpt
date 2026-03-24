"""
Model interfaces for Nemotron and GPT-5.4 Nano.

Both implement the same ModelInterface so evaluator code is model-agnostic.
A MockModel is provided for CI / demo usage when no API keys are set.
"""
from __future__ import annotations

import logging
import os
import re
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass

import config
from scraper import ArduinoBug

logger = logging.getLogger(__name__)

# ── Code block extraction (shared with evaluator) ─────────────────────────────

_CODE_BLOCK_RE = re.compile(r"```(?:cpp|c|arduino|ino)?\n(.*?)```", re.DOTALL)


def extract_code_blocks(text: str) -> list[str]:
    blocks = _CODE_BLOCK_RE.findall(text)
    if not blocks:
        blocks = re.findall(r"```\n?(.*?)```", text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


# ── Response dataclass ────────────────────────────────────────────────────────

@dataclass
class ModelResponse:
    model_name: str
    raw_text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    error: str = ""

    @property
    def word_count(self) -> int:
        return len(self.raw_text.split())

    @property
    def char_count(self) -> int:
        return len(self.raw_text)


# ── Base interface ────────────────────────────────────────────────────────────

class ModelInterface(ABC):
    name: str = "base"

    @abstractmethod
    def fix_bug(self, bug: ArduinoBug) -> ModelResponse:
        """Ask the model to diagnose and fix the given Arduino bug."""

    def _build_prompt(self, bug: ArduinoBug) -> str:
        parts = [
            "You are an expert Arduino / embedded-systems engineer.",
            "Analyse the following bug report and provide:",
            "1. Root cause explanation",
            "2. Fixed code (complete, compilable sketch)",
            "3. Testing recommendations",
            "",
            f"## Bug Title\n{bug.title}",
            f"\n## Description\n{bug.body}",
        ]
        if bug.code_snippet.strip():
            parts.append(f"\n## Original Code\n```cpp\n{bug.code_snippet.strip()}\n```")
        return "\n".join(parts)


# ── OpenAI-compatible client helper ──────────────────────────────────────────

def _openai_chat(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
) -> ModelResponse:
    """Generic OpenAI-compatible chat completion call with timing."""
    import time

    try:
        from openai import OpenAI
    except ImportError as exc:
        return ModelResponse(model_name=model, raw_text="", error=f"openai package missing: {exc}")

    client = OpenAI(api_key=api_key, base_url=base_url)

    t0 = time.monotonic()
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
        )
        elapsed = (time.monotonic() - t0) * 1000
        text = completion.choices[0].message.content or ""
        usage = completion.usage
        return ModelResponse(
            model_name=model,
            raw_text=text,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_ms=elapsed,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        logger.error("API call failed (%s): %s", model, exc)
        return ModelResponse(model_name=model, raw_text="", error=str(exc), latency_ms=elapsed)


# ── Nemotron ─────────────────────────────────────────────────────────────────

class NemotronModel(ModelInterface):
    name = "Nemotron"

    def fix_bug(self, bug: ArduinoBug) -> ModelResponse:
        prompt = self._build_prompt(bug)
        return _openai_chat(
            base_url=config.nemotron_base(),
            api_key=config.nemotron_key(),
            model=config.NEMOTRON_MODEL,
            prompt=prompt,
        )


# ── GPT-5.4 Nano ─────────────────────────────────────────────────────────────

class GPTNanoModel(ModelInterface):
    name = "GPT-Nano"

    def fix_bug(self, bug: ArduinoBug) -> ModelResponse:
        prompt = self._build_prompt(bug)
        return _openai_chat(
            base_url=config.gpt_base(),
            api_key=config.gpt_key(),
            model=config.OPENAI_MODEL,
            prompt=prompt,
        )


# ── Mock model (no API keys required) ────────────────────────────────────────

_MOCK_RESPONSES: dict[str, dict[str, str]] = {
    "i2c": {
        "Nemotron": textwrap.dedent("""
            ## Root Cause
            The I2C bus hang is caused by missing STOP condition. `Wire.endTransmission()`
            defaults to `true` on some platforms but on the AVR HAL you must pass the
            `sendStop` parameter explicitly.

            Additionally at 400 kHz (fast-mode) you should verify your pull-up values:
            with 4.7 kΩ on 5 V the rise time τ = R·C ≈ 4700 × 50pF = 235 ns which is
            within spec, but stray capacitance can push this over the 300 ns limit.

            **Recommendation:** Attach a logic analyser or oscilloscope to SDA/SCL and
            look for SCL stretching events — these indicate a slave is holding the clock
            low, which will eventually starve the master.

            ## Fixed Code
            ```cpp
            #include <Wire.h>
            #define MCP_ADDR 0x20

            void setup() {
              Wire.begin();
              Wire.setClock(400000);
              // Configure all GPIOA pins as outputs
              wireWrite(0x00, 0x00);
            }

            void wireWrite(uint8_t reg, uint8_t val) {
              Wire.beginTransmission(MCP_ADDR);
              Wire.write(reg);
              Wire.write(val);
              uint8_t err = Wire.endTransmission(true);  // explicit STOP
              if (err) {
                // Bus recovery: toggle SCL 9 times to release stuck SDA
                pinMode(SDA, OUTPUT);
                for (int i = 0; i < 9; i++) {
                  digitalWrite(SCL, LOW);  delayMicroseconds(5);
                  digitalWrite(SCL, HIGH); delayMicroseconds(5);
                }
                Wire.begin();  // reinitialise
              }
            }
            ```

            ## Testing
            - Scope SDA/SCL at 1 µs/div during rapid transactions
            - Inject a slave NACK and verify bus-recovery triggers
        """).strip(),
        "GPT-Nano": textwrap.dedent("""
            ## Fix
            Pass `true` to `endTransmission()` so a STOP condition is sent:

            ```cpp
            Wire.endTransmission(true);
            ```

            Without the explicit `true` the driver may send a RESTART instead of STOP,
            leaving SDA asserted and hanging the bus.
        """).strip(),
    },
    "memory": {
        "Nemotron": textwrap.dedent("""
            ## Root Cause
            `dtostrf(val, 20, 6, buf)` requests a minimum field width of 20 characters
            plus the decimal point, 6 fractional digits, sign, and null terminator —
            totalling up to 29 bytes — written into a 16-byte buffer.

            The 13-byte overflow corrupts the `.data` segment or the return address on
            the stack, causing the observed garbage output and spontaneous resets.

            On ATmega devices, SRAM is only 2 KB; a single mis-sized buffer can bring
            the entire runtime down.

            ## Fixed Code
            ```cpp
            // Field width 10, 4 decimal places → max 10 + '.' + 4 + sign + NUL = 17
            // Use 24 to be safe.
            char buf[24];

            void formatSensor(float val) {
              dtostrf(val, 8, 4, buf);
              Serial.println(buf);
            }
            ```

            ## Testing
            - Enable stack-canary checks via `-fstack-protector-all`
            - Run `avr-size` to track RAM usage before and after the fix
        """).strip(),
        "GPT-Nano": textwrap.dedent("""
            ## Fix
            Your buffer is too small. `dtostrf` with width=20 needs at least 22 bytes
            (sign + digits + dot + null). Increase `buf`:

            ```cpp
            char buf[32];   // safe for any reasonable float
            ```

            Or reduce the width:

            ```cpp
            dtostrf(val, 6, 3, buf);  // "x.xxx\0" — 7 chars max
            ```
        """).strip(),
    },
    "peripheral": {
        "Nemotron": textwrap.dedent("""
            ## Root Cause
            The `Servo` library on the Uno uses **Timer1** (16-bit) to generate 50 Hz PWM
            on pins 9 and 10. The SD library uses SPI (pins 11/12/13) with DMA-style
            byte-at-a-time polling.

            During `SD.open()` / `f.close()` the SPI transactions disable interrupts
            (`cli()`) for up to several hundred microseconds. This interrupts Timer1's
            ISR, causing the servo pulse to be stretched or dropped — resulting in jitter.

            Specifically: `TCCR1A` and `TCCR1B` are set by `Servo::attach()`. The SD
            library's `SPI.transfer()` calls inside `SD.begin()` temporarily reconfigure
            the SPI control registers (`SPCR`, `SPSR`) while Timer1 is still running,
            but the real culprit is interrupt latency.

            ## Fixed Code
            ```cpp
            #include <ServoTimer2.h>   // uses Timer2, avoids Timer1 conflict
            #include <SD.h>
            #include <SPI.h>

            ServoTimer2 myServo;
            const int CS_PIN = 4;

            void setup() {
              myServo.attach(9);
              SD.begin(CS_PIN);
            }
            // rest of sketch unchanged
            ```

            Alternatively use a software-PWM servo driver to avoid any hardware timer.

            ## Testing
            - Measure servo pulse width with a scope or `pulseIn()` during SD writes
            - Verify jitter < 10 µs with the fix applied
        """).strip(),
        "GPT-Nano": textwrap.dedent("""
            ## Fix
            The Servo library uses Timer1; the SD library disables interrupts during SPI
            transfers, cutting Timer1's ISR and causing jitter.

            **Option 1** — Use `ServoTimer2` library (Timer2 is free on the Uno):
            ```cpp
            #include <ServoTimer2.h>
            ServoTimer2 myServo;
            ```

            **Option 2** — Buffer SD writes and flush them outside the servo update window.
        """).strip(),
    },
    "watchdog": {
        "Nemotron": textwrap.dedent("""
            ## Root Cause
            512 EEPROM writes × ~3.3 ms each = ~1.7 seconds total. The watchdog is set
            to 250 ms (WDTO_250MS). The first WDT overflow occurs after 250 ms, resetting
            the CPU before setup() finishes, creating an endless reset loop.

            ## Fixed Code
            ```cpp
            #include <avr/wdt.h>
            #include <EEPROM.h>

            void setup() {
              wdt_enable(WDTO_4S);   // 4 s gives enough headroom
              for (int i = 0; i < 512; i++) {
                EEPROM.write(i, i & 0xFF);
                if (i % 64 == 0) wdt_reset();  // pet the dog every 64 writes
              }
              wdt_disable();
            }
            ```
        """).strip(),
        "GPT-Nano": textwrap.dedent("""
            ## Fix
            Call `wdt_reset()` inside the loop to reset the watchdog counter:

            ```cpp
            for (int i = 0; i < 512; i++) {
              EEPROM.write(i, i & 0xFF);
              wdt_reset();   // add this
            }
            ```

            Or increase the timeout to `WDTO_2S` / `WDTO_4S`.
        """).strip(),
    },
    "interrupt": {
        "Nemotron": textwrap.dedent("""
            ## Root Cause
            `IRremote` (v2/v3) hijacks **Timer2** to generate the 38 kHz carrier and to
            time IR pulse widths. `millis()` on the AVR is driven by a Timer0 overflow
            ISR. However, IRremote reconfigures Timer2's prescaler, which on some AVR
            variants shares a clock-select bit with Timer0 causing millis() drift.

            Additionally, IRremote's Timer2 ISR blocks for up to ~70 µs, delaying
            Timer0's overflow ISR and introducing cumulative drift.

            ## Fixed Code
            Upgrade to IRremote ≥ 4.0 and select a non-conflicting timer:
            ```cpp
            #define IR_USE_TIMER1          // use Timer1 instead
            #include <IRremote.hpp>        // v4+ header name
            IRrecv irrecv(11);
            ```

            Or use the `IRLib2` library which allows explicit timer selection.
        """).strip(),
        "GPT-Nano": textwrap.dedent("""
            ## Fix
            IRremote v2/v3 uses Timer2, which conflicts with millis() on some boards.

            Update to IRremote v4+:
            ```cpp
            #define TIMER_INTR_FLAG   // pick a free timer
            #include <IRremote.hpp>
            ```

            Or pin to a specific timer: `#define IR_USE_TIMER1` before the include.
        """).strip(),
    },
    "general": {
        "Nemotron": textwrap.dedent("""
            ## Analysis
            Without more detail I can offer a general diagnostic approach:

            1. Enable verbose compiler output to catch implicit type conversions
            2. Check heap/stack collision via a free-RAM probe:
               ```cpp
               extern int __heap_start, *__brkval;
               int freeRam() {
                 int v; return (int)&v - (__brkval ? (int)__brkval : (int)&__heap_start);
               }
               ```
            3. Use `Serial.println(freeRam())` at strategic points

            ## Testing
            Monitor RAM headroom and narrow down the fault to a specific subsystem.
        """).strip(),
        "GPT-Nano": textwrap.dedent("""
            ## Fix
            Please provide a minimal reproducible sketch. Common causes:
            - Off-by-one in array indexing
            - Missing `Serial.begin()` call
            - Blocking `delay()` inside an ISR
        """).strip(),
    },
}


class MockModel(ModelInterface):
    """Returns deterministic canned responses keyed by bug category."""

    def __init__(self, model_label: str):
        self.name = model_label
        self._label = "Nemotron" if "Nemotron" in model_label or "nemotron" in model_label else "GPT-Nano"

    def fix_bug(self, bug: ArduinoBug) -> ModelResponse:
        import time
        import random

        cat = bug.category if bug.category in _MOCK_RESPONSES else "general"
        text = _MOCK_RESPONSES[cat].get(self._label, _MOCK_RESPONSES["general"][self._label])
        # Simulate latency variance
        latency = random.uniform(300, 900) if self._label == "Nemotron" else random.uniform(100, 400)
        time.sleep(latency / 1000)  # simulate network roundtrip

        return ModelResponse(
            model_name=self.name,
            raw_text=text,
            prompt_tokens=len(self._build_prompt(bug).split()),
            completion_tokens=len(text.split()),
            latency_ms=latency,
        )


# ── Factory ───────────────────────────────────────────────────────────────────

def get_models(force_mock: bool = False) -> tuple[ModelInterface, ModelInterface]:
    """
    Return (nemotron, gpt_nano).
    Falls back to MockModel when keys are absent or force_mock=True.
    """
    if force_mock or config.mock_mode():
        logger.info("Running in MOCK mode (no API keys configured)")
        return (
            MockModel(config.NEMOTRON_MODEL),
            MockModel(config.OPENAI_MODEL),
        )
    return NemotronModel(), GPTNanoModel()
