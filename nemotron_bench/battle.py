#!/usr/bin/env python3
"""
battle.py — main entry point for the Arduino AI Battle benchmark.

Usage:
  python -m nemotron_bench.battle --count 50
  python -m nemotron_bench.battle --count 5 --mock      # force mock mode
  python -m nemotron_bench.battle --count 10 --no-html  # JSON only
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich import print as rprint

load_dotenv()

from . import config
from .scraper import fetch_bugs, ArduinoBug
from .models import get_models, ModelInterface, ModelResponse
from .evaluator import evaluate, EvalResult
from .reporter import generate_report, save_json

console = Console()
logger = logging.getLogger(__name__)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arduino AI Battle — benchmark Nemotron vs GPT-4.1 on real forum bugs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--count", type=int, default=config.SCRAPE_COUNT,
                        help=f"Number of bugs to evaluate (default: {config.SCRAPE_COUNT})")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="Force mock mode (no API calls)")
    parser.add_argument("--no-html", action="store_true", default=False,
                        help="Skip HTML report generation")
    parser.add_argument("--no-json", action="store_true", default=False,
                        help="Skip JSON output")
    parser.add_argument("--output-dir", type=str, default=config.OUTPUT_DIR,
                        help=f"Output directory (default: {config.OUTPUT_DIR})")
    parser.add_argument("--report", type=str, default=None,
                        help="Custom path for the HTML report file")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel workers for model calls (default: 1)")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


# ── Core logic ────────────────────────────────────────────────────────────────

def run_battle(
    bugs: list[ArduinoBug],
    nemotron: ModelInterface,
    gpt: ModelInterface,
    workers: int = 1,
) -> list[EvalResult]:
    """Query both models for each bug and evaluate. Returns list of EvalResult."""
    results: list[EvalResult] = []

    def process_bug(bug: ArduinoBug) -> EvalResult:
        nem_resp = nemotron.fix_bug(bug)
        gpt_resp = gpt.fix_bug(bug)
        return evaluate(bug, nem_resp, gpt_resp)

    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating bugs…", total=len(bugs))

        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(process_bug, bug): bug for bug in bugs}
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        bug = futures[future]
                        logger.error("Error processing '%s': %s", bug.title[:40], exc)
                    progress.advance(task)
        else:
            for bug in bugs:
                try:
                    result = process_bug(bug)
                    results.append(result)
                except Exception as exc:
                    logger.error("Error processing '%s': %s", bug.title[:40], exc)
                progress.advance(task)

    return results


# ── Summary printer ───────────────────────────────────────────────────────────

def print_summary(results: list[EvalResult]) -> None:
    if not results:
        console.print("[red]No results to summarise.[/red]")
        return

    total = len(results)
    nem_wins = sum(1 for r in results if r.winner == "nemotron")
    gpt_wins = sum(1 for r in results if r.winner == "gpt")
    ties = total - nem_wins - gpt_wins

    nem_avg = sum(r.nemotron_total for r in results) / total
    gpt_avg = sum(r.gpt_total for r in results) / total
    nem_comp = sum(r.nemotron_compilable for r in results) / total
    gpt_comp = sum(r.gpt_compilable for r in results) / total
    nem_corr = sum(r.nemotron_correctness for r in results) / total
    gpt_corr = sum(r.gpt_correctness for r in results) / total
    nem_verb = sum(r.nemotron_verbosity for r in results) / total
    gpt_verb = sum(r.gpt_verbosity for r in results) / total
    nem_lat = sum(r.nemotron_response.latency_ms for r in results) / total
    gpt_lat = sum(r.gpt_response.latency_ms for r in results) / total

    table = Table(title="⚡ Battle Summary", show_header=True, header_style="bold")
    table.add_column("Metric", style="dim")
    table.add_column("Nemotron", style="green")
    table.add_column("GPT-4.1", style="cyan")

    table.add_row("Wins", str(nem_wins), str(gpt_wins))
    table.add_row("Ties", str(ties), "—")
    table.add_row("Avg Total Score", f"{nem_avg:.3f}", f"{gpt_avg:.3f}")
    table.add_row("Avg Compilability", f"{nem_comp:.3f}", f"{gpt_comp:.3f}")
    table.add_row("Avg Correctness", f"{nem_corr:.3f}", f"{gpt_corr:.3f}")
    table.add_row("Avg Verbosity", f"{nem_verb:.3f}", f"{gpt_verb:.3f}")
    table.add_row("Avg Latency (ms)", f"{nem_lat:.0f}", f"{gpt_lat:.0f}")

    console.print()
    console.print(table)

    # Per-category breakdown
    categories = sorted({r.bug.category for r in results})
    if len(categories) > 1:
        cat_table = Table(title="Per-Category Winners", show_header=True, header_style="bold")
        cat_table.add_column("Category", style="dim")
        cat_table.add_column("Nemotron Wins", style="green")
        cat_table.add_column("GPT-4.1 Wins", style="cyan")
        cat_table.add_column("Ties")

        for cat in categories:
            cat_results = [r for r in results if r.bug.category == cat]
            nw = sum(1 for r in cat_results if r.winner == "nemotron")
            gw = sum(1 for r in cat_results if r.winner == "gpt")
            tw = len(cat_results) - nw - gw
            cat_table.add_row(cat, str(nw), str(gw), str(tw))

        console.print()
        console.print(cat_table)


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s — %(message)s",
    )

    # Override output dir if specified
    if args.output_dir != config.OUTPUT_DIR:
        os.environ["OUTPUT_DIR"] = args.output_dir

    console.print()
    console.rule("[bold]⚡ Arduino AI Battle[/bold]")
    console.print(f"  Nemotron model : [green]{config.NEMOTRON_MODEL}[/green]")
    console.print(f"  GPT model      : [cyan]{config.OPENAI_MODEL}[/cyan]")

    in_mock = args.mock or config.mock_mode()
    if in_mock:
        console.print("  Mode           : [yellow]MOCK[/yellow] (no API keys — using canned responses)")
    else:
        console.print("  Mode           : [bold green]LIVE[/bold green]")

    console.print(f"  Bugs requested : {args.count}")
    console.print()

    # 1. Fetch bugs
    with console.status("Fetching Arduino forum bugs…"):
        bugs = fetch_bugs(args.count)
    console.print(f"[green]✓[/green] Loaded {len(bugs)} bugs")

    # 2. Load models
    nemotron, gpt = get_models(force_mock=args.mock)

    # 3. Run battle
    t0 = time.monotonic()
    results = run_battle(bugs, nemotron, gpt, workers=args.workers)
    elapsed = time.monotonic() - t0
    console.print(f"[green]✓[/green] Evaluated {len(results)} bugs in {elapsed:.1f}s")

    # 4. Print summary
    print_summary(results)

    # 5. Write outputs
    os.makedirs(args.output_dir, exist_ok=True)

    if not args.no_json:
        json_path = os.path.join(args.output_dir, "battle_results.json")
        save_json(results, json_path)
        console.print(f"[green]✓[/green] JSON → {json_path}")

    if not args.no_html:
        report_path = args.report or os.path.join(args.output_dir, config.REPORT_FILENAME)
        generate_report(results, report_path)
        console.print(f"[green]✓[/green] HTML report → {report_path}")

    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
