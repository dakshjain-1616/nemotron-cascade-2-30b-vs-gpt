"""
Arduino forum scraper — fetches real bug reports from forum.arduino.cc.

Falls back to a curated set of seed bugs when the network is unavailable
or when fewer live bugs than requested are found.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from . import config

logger = logging.getLogger(__name__)

# ── Domain model ─────────────────────────────────────────────────────────────

@dataclass
class ArduinoBug:
    """One scraped (or seed) bug report."""
    title: str
    body: str
    url: str
    category: str = "general"
    code_snippet: str = ""
    tags: list[str] = field(default_factory=list)

    # Human-readable expected behaviour for tests
    expected_nemotron_behavior: str = ""
    expected_gpt_behavior: str = ""


# ── Curated seed bugs (used as fallback / for testing) ──────────────────────

SEED_BUGS: list[ArduinoBug] = [
    ArduinoBug(
        title="I2C timing issue — SDA line not releasing after transaction",
        category="i2c",
        url="seed://i2c-timing",
        tags=["i2c", "timing", "wire"],
        body=(
            "I'm using Wire.h to communicate with an MCP23017 GPIO expander on an Arduino Uno. "
            "After a few hundred transactions the SDA line gets stuck low and the bus hangs. "
            "My SCL frequency is set to 400 kHz (fast mode). "
            "I've added 4.7kΩ pull-ups to both SDA and SCL."
        ),
        code_snippet="""
#include <Wire.h>
#define MCP_ADDR 0x20

void setup() {
  Wire.begin();
  Wire.setClock(400000);
}

void loop() {
  Wire.beginTransmission(MCP_ADDR);
  Wire.write(0x00);  // IODIRA register
  Wire.write(0x00);  // all outputs
  Wire.endTransmission();   // <-- missing stop condition?
  delay(10);
}
""",
        expected_nemotron_behavior=(
            "Suggests using an oscilloscope or logic analyser to capture SDA/SCL "
            "waveforms and identifies clock-stretching issues"
        ),
        expected_gpt_behavior=(
            "Provides a concise fix: call Wire.endTransmission(true) to send a STOP "
            "condition and reset the bus"
        ),
    ),
    ArduinoBug(
        title="Memory corruption — array out of bounds overwrites stack",
        category="memory",
        url="seed://memory-corruption",
        tags=["memory", "buffer", "stack"],
        body=(
            "My Arduino Mega sketch runs fine for ~30 seconds then produces garbage serial output "
            "and occasionally resets. I have a global char array I use as a scratch buffer."
        ),
        code_snippet="""
char buf[16];

void formatSensor(float val) {
  // BUG: dtostrf writes up to 8 chars + null, but can exceed 16
  dtostrf(val, 20, 6, buf);   // width=20 > sizeof(buf)
  Serial.println(buf);
}

void loop() {
  formatSensor(analogRead(A0) * 5.0 / 1023.0);
  delay(100);
}
""",
        expected_nemotron_behavior=(
            "Detects the buffer overflow and explains how it corrupts adjacent stack frames"
        ),
        expected_gpt_behavior=(
            "Explains the overflow clearly and suggests increasing buf to at least 22 bytes "
            "or reducing the width parameter"
        ),
    ),
    ArduinoBug(
        title="Peripheral conflict — SPI and SD card clash with Timer1 PWM",
        category="peripheral",
        url="seed://peripheral-conflict",
        tags=["spi", "sd", "timer", "pwm", "register"],
        body=(
            "I'm driving a servo on pin 9 with the Servo library while simultaneously reading "
            "from an SD card over SPI. The servo jitters badly whenever an SD read occurs. "
            "Board: Arduino Uno R3."
        ),
        code_snippet="""
#include <Servo.h>
#include <SD.h>
#include <SPI.h>

Servo myServo;
const int CS_PIN = 4;

void setup() {
  myServo.attach(9);        // uses Timer1
  SD.begin(CS_PIN);         // SPI on pins 11,12,13
}

void loop() {
  myServo.write(90);
  File f = SD.open("log.txt", FILE_WRITE);
  if (f) {
    f.println("data");
    f.close();
  }
  delay(20);
}
""",
        expected_nemotron_behavior=(
            "Identifies the Timer1 / SPI register clash in detail, noting that SD.begin() "
            "briefly disables interrupts and explaining the TCCR1A/TCCR1B register conflict"
        ),
        expected_gpt_behavior=(
            "Recommends using a timer-based servo library that avoids Timer1 or moving "
            "the servo to a dedicated timer"
        ),
    ),
    ArduinoBug(
        title="Watchdog reset loop — WDT not disabled before long flash write",
        category="watchdog",
        url="seed://watchdog-reset",
        tags=["watchdog", "wdt", "eeprom", "flash"],
        body=(
            "My sketch writes calibration data to EEPROM every boot. After adding watchdog "
            "support the device enters a reset loop. ATmega328P running at 16 MHz."
        ),
        code_snippet="""
#include <avr/wdt.h>
#include <EEPROM.h>

void setup() {
  wdt_enable(WDTO_250MS);   // 250 ms watchdog
  for (int i = 0; i < 512; i++) {
    EEPROM.write(i, i & 0xFF);   // each write takes ~3.3 ms → 512*3.3 ≈ 1.7 s
  }
  wdt_disable();
}
""",
        expected_nemotron_behavior=(
            "Explains that 512 EEPROM writes at 3.3 ms each takes ~1.7 s, which exceeds "
            "the 250 ms WDT window, causing repeated resets"
        ),
        expected_gpt_behavior=(
            "Suggests calling wdt_reset() inside the loop or increasing WDT timeout to "
            "WDTO_2S / WDTO_4S"
        ),
    ),
    ArduinoBug(
        title="Interrupt conflict — millis() drift when using Timer2 for IR receive",
        category="interrupt",
        url="seed://interrupt-conflict",
        tags=["interrupt", "timer", "millis", "ir", "irremote"],
        body=(
            "After adding the IRremote library my millis() values drift by roughly 10% "
            "over a few minutes. The IR receiver works fine but time-based logic breaks."
        ),
        code_snippet="""
#include <IRremote.h>

IRrecv irrecv(11);
decode_results results;

unsigned long lastAction = 0;
const unsigned long INTERVAL = 5000;

void loop() {
  if (irrecv.decode(&results)) {
    irrecv.resume();
  }
  if (millis() - lastAction >= INTERVAL) {
    lastAction = millis();
    doPeriodicTask();
  }
}
""",
        expected_nemotron_behavior=(
            "Identifies that IRremote reconfigures Timer2 which is also used by millis(), "
            "causing the drift"
        ),
        expected_gpt_behavior=(
            "Recommends using IRremote v4+ which uses a different timer or explicitly "
            "selecting a non-conflicting timer via IR_TIMER"
        ),
    ),
]


# ── Live scraper ──────────────────────────────────────────────────────────────

_BUG_KEYWORDS = [
    "bug", "doesn't work", "not working", "glitch",
    "hang", "freeze", "crash", "error", "broken",
    "timing", "memory", "overflow", "interrupt", "conflict",
]

_CATEGORY_KEYWORDS = {
    "i2c": ["i2c", "wire", "sda", "scl", "twi"],
    "spi": ["spi", "mosi", "miso", "sck"],
    "memory": ["memory", "sram", "stack", "heap", "overflow", "buffer"],
    "timer": ["timer", "millis", "micros", "pwm", "timer0", "timer1", "timer2"],
    "interrupt": ["interrupt", "isr", "sei", "cli", "attachinterrupt"],
    "watchdog": ["watchdog", "wdt", "wdto"],
    "peripheral": ["servo", "sd", "lcd", "uart", "serial"],
}


def _classify(text: str) -> str:
    lower = text.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return cat
    return "general"


def _extract_code(soup: BeautifulSoup) -> str:
    snippets = []
    # Prefer <pre><code> blocks first, then bare <code> tags
    for tag in soup.select("pre > code, pre, code"):
        text = tag.get_text(strip=True)
        if len(text) > 3:
            snippets.append(text)
    return "\n\n".join(snippets[:3])  # at most 3 snippets


def _parse_topic(url: str, session: requests.Session) -> Optional[ArduinoBug]:
    try:
        resp = session.get(url, timeout=config.SCRAPE_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.debug("Failed to fetch topic %s: %s", url, exc)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    title_tag = soup.select_one("h1.fancy-title, h1[data-post-id]")
    if not title_tag:
        return None

    title = title_tag.get_text(strip=True)
    first_post = soup.select_one("div.cooked")
    body = first_post.get_text(" ", strip=True)[:2000] if first_post else ""
    code = _extract_code(soup)
    category = _classify(title + " " + body)

    return ArduinoBug(
        title=title,
        body=body,
        url=url,
        category=category,
        code_snippet=code,
    )


def _search_forum(count: int, session: requests.Session) -> list[ArduinoBug]:
    """Search forum.arduino.cc for bug-related topics via the Discourse API."""
    bugs: list[ArduinoBug] = []
    page = 0

    while len(bugs) < count:
        params = {
            "q": "bug OR error OR broken OR hang OR crash code",
            "page": page,
        }
        try:
            resp = session.get(
                f"{config.ARDUINO_FORUM_URL}/search.json",
                params=params,
                timeout=config.SCRAPE_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Forum search failed (page %d): %s", page, exc)
            break

        topics = data.get("topics", [])
        if not topics:
            break

        for topic in topics:
            if len(bugs) >= count:
                break
            slug = topic.get("slug", "")
            topic_id = topic.get("id", "")
            if not slug or not topic_id:
                continue
            topic_url = f"{config.ARDUINO_FORUM_URL}/t/{slug}/{topic_id}"
            bug = _parse_topic(topic_url, session)
            if bug:
                bugs.append(bug)
                logger.debug("Scraped: %s", bug.title[:60])
            time.sleep(config.SCRAPE_DELAY)

        page += 1

    return bugs


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_bugs(count: int = config.SCRAPE_COUNT) -> list[ArduinoBug]:
    """
    Return ``count`` ArduinoBug objects.

    Tries live scraping first; supplements with seed bugs when live results
    are insufficient or the network is unavailable.
    """
    session = requests.Session()
    session.headers["User-Agent"] = (
        "arduino-ai-battle/1.0 (benchmark tool; contact: neo@heyneo.so)"
    )

    live_bugs: list[ArduinoBug] = []
    try:
        live_bugs = _search_forum(count, session)
        logger.info("Scraped %d live bugs from forum", len(live_bugs))
    except Exception as exc:
        logger.warning("Live scraping failed entirely: %s", exc)

    # Fill remainder with seed bugs (cycling if needed)
    combined = list(live_bugs)
    if len(combined) < count:
        needed = count - len(combined)
        for i in range(needed):
            combined.append(SEED_BUGS[i % len(SEED_BUGS)])

    return combined[:count]
