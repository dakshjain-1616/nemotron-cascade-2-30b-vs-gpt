"""Central configuration — every value from env vars, zero hardcoding."""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes")


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


# ── OpenRouter (single key for both models) ───────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"

# ── NVIDIA / Nemotron ────────────────────────────────────────────────────────
NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_API_BASE: str = os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")
NEMOTRON_MODEL: str = os.getenv("NEMOTRON_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1")

# ── OpenAI / GPT ─────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "openai/gpt-4.1")

# ── Arduino CLI ──────────────────────────────────────────────────────────────
ARDUINO_CLI_PATH: str = os.getenv("ARDUINO_CLI_PATH", "arduino-cli")
ARDUINO_FQBN: str = os.getenv("ARDUINO_FQBN", "arduino:avr:uno")
ARDUINO_COMPILE_TIMEOUT: int = _int("ARDUINO_COMPILE_TIMEOUT", 30)

# ── Scraper ───────────────────────────────────────────────────────────────────
ARDUINO_FORUM_URL: str = os.getenv("ARDUINO_FORUM_URL", "https://forum.arduino.cc")
SCRAPE_COUNT: int = _int("SCRAPE_COUNT", 50)
SCRAPE_TIMEOUT: int = _int("SCRAPE_TIMEOUT", 15)
SCRAPE_DELAY: float = _float("SCRAPE_DELAY", 1.0)

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./results")
REPORT_FILENAME: str = os.getenv("REPORT_FILENAME", "battle_report.html")

# ── General ───────────────────────────────────────────────────────────────────
DEBUG: bool = _bool("DEBUG")
MAX_TOKENS: int = _int("MAX_TOKENS", 1024)
TEMPERATURE: float = _float("TEMPERATURE", 0.2)


def has_openrouter_key() -> bool:
    return bool(OPENROUTER_API_KEY and len(OPENROUTER_API_KEY) > 10)


def has_nvidia_key() -> bool:
    return bool(NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("nvapi-xxx"))


def has_openai_key() -> bool:
    return bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-xxx"))


def mock_mode() -> bool:
    """Return True when no usable API key is configured."""
    return not (has_openrouter_key() or (has_nvidia_key() and has_openai_key()))


def nemotron_key() -> str:
    return OPENROUTER_API_KEY if has_openrouter_key() else NVIDIA_API_KEY


def nemotron_base() -> str:
    return OPENROUTER_API_BASE if has_openrouter_key() else NVIDIA_API_BASE


def gpt_key() -> str:
    return OPENROUTER_API_KEY if has_openrouter_key() else OPENAI_API_KEY


def gpt_base() -> str:
    return OPENROUTER_API_BASE if has_openrouter_key() else OPENAI_API_BASE
