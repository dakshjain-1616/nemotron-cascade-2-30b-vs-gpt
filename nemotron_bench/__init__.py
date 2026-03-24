"""
Nemotron Cascade 3 vs GPT-4.1 — Arduino firmware bug benchmark.
"""
from .battle import run_battle, parse_args
from .models import get_models, MockModel, ModelResponse
from .evaluator import evaluate, EvalResult
from .scraper import SEED_BUGS, fetch_bugs, ArduinoBug

__version__ = "1.0.0"
__all__ = [
    "run_battle", "parse_args",
    "get_models", "MockModel", "ModelResponse",
    "evaluate", "EvalResult",
    "SEED_BUGS", "fetch_bugs", "ArduinoBug",
]
