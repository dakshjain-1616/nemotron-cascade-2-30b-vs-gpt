#!/usr/bin/env python3
"""
demo.py — zero-config runnable demo for Arduino AI Battle.

Automatically detects missing API keys and switches to mock mode.
Runs in under 60 seconds by default (uses 5 seed bugs, mock responses).
"""
from __future__ import annotations

import os
import sys
import time

# Force mock mode when keys are absent (set before loading config)
def _patch_env_defaults():
    """Ensure the demo always works even with empty .env."""
    os.environ.setdefault("OUTPUT_DIR", "./demo_results")
    os.environ.setdefault("REPORT_FILENAME", "demo_report.html")
    os.environ.setdefault("SCRAPE_COUNT", "5")
    os.environ.setdefault("SCRAPE_DELAY", "0")   # no delay in demo

_patch_env_defaults()

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel

console = Console()


def _has_key(var: str, bad_prefix: str) -> bool:
    val = os.getenv(var, "")
    return bool(val) and not val.startswith(bad_prefix)


def main() -> int:
    console.print()
    console.print(Panel.fit(
        "[bold]⚡ Arduino AI Battle — Demo[/bold]\n"
        "Nemotron Cascade 3 vs GPT-5.4 Nano on real Arduino bugs",
        border_style="green",
    ))

    # ── Key detection ──────────────────────────────────────────────────────────
    has_nvidia = _has_key("NVIDIA_API_KEY", "nvapi-xxx")
    has_openai = _has_key("OPENAI_API_KEY", "sk-xxx")
    mock_mode = not (has_nvidia and has_openai)

    if mock_mode:
        console.print()
        console.print(
            "[yellow]No API keys detected → running in MOCK mode.[/yellow]\n"
            "Set NVIDIA_API_KEY and OPENAI_API_KEY in .env for live model calls.\n"
        )
    else:
        console.print("[green]API keys detected → running in LIVE mode.[/green]\n")

    # ── Load 5 seed bugs (fast) ────────────────────────────────────────────────
    from nemotron_bench.scraper import SEED_BUGS
    bugs = SEED_BUGS[:5]
    console.print(f"[dim]Using {len(bugs)} seed bugs for demo:[/dim]")
    for b in bugs:
        console.print(f"  • [{b.category}] {b.title[:65]}")
    console.print()

    # ── Run battle ─────────────────────────────────────────────────────────────
    from nemotron_bench.models import get_models
    from nemotron_bench.evaluator import evaluate
    from nemotron_bench.reporter import generate_report, save_json

    nemotron, gpt = get_models(force_mock=mock_mode)

    results = []
    t0 = time.monotonic()

    for i, bug in enumerate(bugs, 1):
        console.print(f"[dim]({i}/{len(bugs)})[/dim] Evaluating: {bug.title[:55]}…")
        nem_resp = nemotron.fix_bug(bug)
        gpt_resp = gpt.fix_bug(bug)
        result = evaluate(bug, nem_resp, gpt_resp)
        results.append(result)

        # Quick per-bug output
        winner_str = {
            "nemotron": f"[green]Nemotron[/green] ({result.nemotron_total:.2f})",
            "gpt": f"[cyan]GPT-5.4 Nano[/cyan] ({result.gpt_total:.2f})",
            "tie": f"[yellow]Tie[/yellow]",
        }.get(result.winner, result.winner)
        console.print(f"         Winner: {winner_str}")

    elapsed = time.monotonic() - t0
    console.print()
    console.print(f"[green]✓[/green] Completed {len(results)} evaluations in {elapsed:.1f}s")

    # ── Aggregate ──────────────────────────────────────────────────────────────
    total = len(results)
    nem_wins = sum(1 for r in results if r.winner == "nemotron")
    gpt_wins = sum(1 for r in results if r.winner == "gpt")
    ties = total - nem_wins - gpt_wins
    nem_avg = sum(r.nemotron_total for r in results) / total
    gpt_avg = sum(r.gpt_total for r in results) / total

    console.print()
    console.print(f"  [bold]Nemotron[/bold] wins: [green]{nem_wins}[/green]  |  "
                  f"[bold]GPT-5.4 Nano[/bold] wins: [cyan]{gpt_wins}[/cyan]  |  "
                  f"Ties: [yellow]{ties}[/yellow]")
    console.print(f"  Avg scores — Nemotron: [green]{nem_avg:.3f}[/green]  "
                  f"GPT-5.4 Nano: [cyan]{gpt_avg:.3f}[/cyan]")

    # ── Write outputs ──────────────────────────────────────────────────────────
    out_dir = os.getenv("OUTPUT_DIR", "./demo_results")
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "demo_results.json")
    save_json(results, json_path)

    report_path = os.path.join(out_dir, "demo_report.html")
    generate_report(results, report_path)

    console.print()
    console.print(f"[green]✓[/green] JSON  → {json_path}")
    console.print(f"[green]✓[/green] HTML  → {report_path}")
    console.print()
    console.print("[dim]Open the HTML file in your browser for the interactive report.[/dim]")
    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
