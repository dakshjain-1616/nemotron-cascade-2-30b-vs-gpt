"""
HTML report generator.

Produces an interactive side-by-side comparison with diff highlighting,
score charts, and per-bug drill-down panels.
"""
from __future__ import annotations

import difflib
import html
import json
import os
from datetime import datetime, timezone
from typing import Sequence

from .evaluator import EvalResult
from . import config

# ── HTML template ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Arduino AI Battle Report</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d2e; --card: #1e2235;
    --nem: #76b900; --gpt: #10a37f; --tie: #888;
    --text: #e0e0e0; --muted: #888; --code-bg: #12151f;
    --border: #2e3250;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }
  a { color: #7ba7d8; }

  /* ── Layout ── */
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 24px 32px; }
  header h1 { font-size: 1.6rem; margin-bottom: 4px; }
  header .subtitle { color: var(--muted); font-size: 0.9rem; }
  main { max-width: 1400px; margin: 0 auto; padding: 24px 16px; }

  /* ── Summary cards ── */
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; text-align: center; }
  .stat-card .value { font-size: 2rem; font-weight: 700; }
  .stat-card .label { color: var(--muted); font-size: 0.8rem; margin-top: 4px; }
  .nem-color { color: var(--nem); }
  .gpt-color { color: var(--gpt); }

  /* ── Bar chart ── */
  .chart-section { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 32px; }
  .chart-section h2 { margin-bottom: 16px; font-size: 1.1rem; }
  .bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .bar-label { width: 90px; font-size: 0.8rem; color: var(--muted); }
  .bar-outer { flex: 1; background: #2a2d40; border-radius: 4px; height: 22px; }
  .bar-inner { height: 100%; border-radius: 4px; transition: width 0.3s; display: flex; align-items: center; padding-left: 8px; font-size: 0.75rem; white-space: nowrap; }
  .bar-nem { background: var(--nem); color: #000; }
  .bar-gpt { background: var(--gpt); color: #000; }

  /* ── Bug cards ── */
  .section-title { font-size: 1.2rem; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
  .bug-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 20px; overflow: hidden; }
  .bug-header { padding: 16px 20px; cursor: pointer; display: flex; align-items: center; gap: 12px; }
  .bug-header:hover { background: #242840; }
  .bug-title { flex: 1; font-size: 0.95rem; }
  .category-badge { font-size: 0.7rem; padding: 3px 8px; border-radius: 12px; background: #2e3250; color: var(--muted); }
  .winner-badge { font-size: 0.75rem; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
  .winner-nemotron { background: rgba(118,185,0,0.15); color: var(--nem); }
  .winner-gpt { background: rgba(16,163,127,0.15); color: var(--gpt); }
  .winner-tie { background: rgba(136,136,136,0.15); color: var(--tie); }
  .chevron { color: var(--muted); transition: transform 0.2s; }
  .bug-body { display: none; padding: 0 20px 20px; }
  .bug-body.open { display: block; }

  /* ── Side-by-side diff ── */
  .side-by-side { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
  @media (max-width: 768px) { .side-by-side { grid-template-columns: 1fr; } }
  .model-panel { background: var(--code-bg); border-radius: 8px; padding: 16px; }
  .model-panel h3 { font-size: 0.85rem; margin-bottom: 12px; }
  .model-panel pre { white-space: pre-wrap; word-break: break-word; font-size: 0.78rem; line-height: 1.5; font-family: 'Fira Code', 'Cascadia Code', monospace; }

  /* ── Scores row ── */
  .scores-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  .score-pill { font-size: 0.72rem; padding: 3px 8px; border-radius: 8px; background: #2e3250; }

  /* ── Diff view ── */
  .diff-section { margin-top: 16px; }
  .diff-section h3 { font-size: 0.85rem; color: var(--muted); margin-bottom: 8px; }
  .diff-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; font-family: monospace; }
  .diff-table td { padding: 2px 8px; vertical-align: top; white-space: pre-wrap; word-break: break-all; }
  .diff-add { background: rgba(16,163,127,0.12); color: #7ec8a8; }
  .diff-rem { background: rgba(220,50,50,0.12); color: #e08080; }
  .diff-same { color: var(--muted); }
  .diff-hdr { background: #1a1d2e; color: var(--muted); padding: 4px 8px; font-style: italic; }

  /* ── Original bug ── */
  .original-bug { background: #12151f; border-left: 3px solid #444; border-radius: 4px; padding: 12px 16px; margin-top: 16px; }
  .original-bug h3 { font-size: 0.8rem; color: var(--muted); margin-bottom: 8px; }
  .original-bug pre { font-size: 0.77rem; white-space: pre-wrap; word-break: break-word; font-family: monospace; color: #b0b8d0; }

  /* ── Footer ── */
  footer { text-align: center; padding: 40px 16px; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); margin-top: 40px; }
  footer a { color: var(--muted); }
</style>
</head>
<body>
<header>
  <h1>⚡ Arduino AI Battle Report</h1>
  <div class="subtitle">
    <strong style="color:var(--nem)">{{ nemotron_model }}</strong>
    vs
    <strong style="color:var(--gpt)">{{ gpt_model }}</strong>
    &nbsp;·&nbsp; Generated {{ timestamp }}
    &nbsp;·&nbsp; {{ total_bugs }} bugs evaluated
  </div>
</header>
<main>

  <!-- Summary cards -->
  <div class="summary-grid">
    <div class="stat-card">
      <div class="value nem-color">{{ nem_wins }}</div>
      <div class="label">Nemotron Wins</div>
    </div>
    <div class="stat-card">
      <div class="value gpt-color">{{ gpt_wins }}</div>
      <div class="label">GPT-Nano Wins</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color:var(--tie)">{{ ties }}</div>
      <div class="label">Ties</div>
    </div>
    <div class="stat-card">
      <div class="value nem-color">{{ nem_avg_score }}</div>
      <div class="label">Nemotron Avg Score</div>
    </div>
    <div class="stat-card">
      <div class="value gpt-color">{{ gpt_avg_score }}</div>
      <div class="label">GPT-Nano Avg Score</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color:#a88">{{ nem_avg_latency }}ms</div>
      <div class="label">Nemotron Avg Latency</div>
    </div>
  </div>

  <!-- Bar chart: dimension breakdown -->
  <div class="chart-section">
    <h2>Score Breakdown by Dimension</h2>
    {{ dimension_chart_html }}
  </div>

  <!-- Per-bug results -->
  <div class="section-title">Per-Bug Results ({{ total_bugs }} bugs)</div>
  {{ bug_cards_html }}

</main>
<footer>
  Arduino AI Battle &mdash; benchmarking embedded AI on real forum bugs.<br/>
  Built autonomously using <a href="https://heyneo.so">NEO - your autonomous AI Agent</a>
</footer>
<script>
document.querySelectorAll('.bug-header').forEach(h => {
  h.addEventListener('click', () => {
    const body = h.nextElementSibling;
    const chev = h.querySelector('.chevron');
    body.classList.toggle('open');
    chev.textContent = body.classList.contains('open') ? '▲' : '▼';
  });
});
</script>
</body>
</html>
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v * 100:.0f}%"


def _bar(label: str, nem_val: float, gpt_val: float) -> str:
    nem_w = int(nem_val * 100)
    gpt_w = int(gpt_val * 100)
    return (
        f'<div class="bar-row">'
        f'  <div class="bar-label">{html.escape(label)}</div>'
        f'  <div class="bar-outer">'
        f'    <div class="bar-inner bar-nem" style="width:{nem_w}%">'
        f'      {"Nemotron " + _pct(nem_val) if nem_w > 15 else ""}</div>'
        f'  </div>'
        f'</div>'
        f'<div class="bar-row">'
        f'  <div class="bar-label"></div>'
        f'  <div class="bar-outer">'
        f'    <div class="bar-inner bar-gpt" style="width:{gpt_w}%">'
        f'      {"GPT-Nano " + _pct(gpt_val) if gpt_w > 15 else ""}</div>'
        f'  </div>'
        f'</div>'
    )


def _render_diff(nem_text: str, gpt_text: str) -> str:
    """Render a unified diff between the two responses."""
    nem_lines = nem_text.splitlines(keepends=True)
    gpt_lines = gpt_text.splitlines(keepends=True)
    differ = difflib.unified_diff(nem_lines, gpt_lines, fromfile="Nemotron", tofile="GPT-Nano", n=2)
    rows: list[str] = []
    for line in list(differ)[:80]:  # cap to 80 lines in report
        esc = html.escape(line.rstrip("\n"))
        if line.startswith("+++") or line.startswith("---"):
            rows.append(f'<tr class="diff-hdr"><td colspan="2">{esc}</td></tr>')
        elif line.startswith("+"):
            rows.append(f'<tr class="diff-add"><td>+</td><td>{esc[1:]}</td></tr>')
        elif line.startswith("-"):
            rows.append(f'<tr class="diff-rem"><td>-</td><td>{esc[1:]}</td></tr>')
        elif line.startswith("@"):
            rows.append(f'<tr class="diff-hdr"><td colspan="2">{esc}</td></tr>')
        else:
            rows.append(f'<tr class="diff-same"><td> </td><td>{esc}</td></tr>')
    if not rows:
        return "<p style='color:var(--muted);font-size:0.8rem'>Responses are identical.</p>"
    return f'<table class="diff-table">{"".join(rows)}</table>'


def _render_bug_card(result: EvalResult, index: int) -> str:
    bug = result.bug
    winner = result.winner
    winner_class = f"winner-{winner}"
    winner_text = {"nemotron": "Nemotron wins", "gpt": "GPT-Nano wins", "tie": "Tie"}.get(winner, winner)

    nem_r = result.nemotron_response
    gpt_r = result.gpt_response

    nem_scores = (
        f'<span class="score-pill">Compile: {_pct(result.nemotron_compilable)}</span>'
        f'<span class="score-pill">Correct: {_pct(result.nemotron_correctness)}</span>'
        f'<span class="score-pill">Verbose: {_pct(result.nemotron_verbosity)}</span>'
        f'<span class="score-pill" style="font-weight:700">Total: {_pct(result.nemotron_total)}</span>'
        f'<span class="score-pill">{nem_r.latency_ms:.0f}ms</span>'
        f'<span class="score-pill">{nem_r.word_count}w</span>'
    )
    gpt_scores = (
        f'<span class="score-pill">Compile: {_pct(result.gpt_compilable)}</span>'
        f'<span class="score-pill">Correct: {_pct(result.gpt_correctness)}</span>'
        f'<span class="score-pill">Verbose: {_pct(result.gpt_verbosity)}</span>'
        f'<span class="score-pill" style="font-weight:700">Total: {_pct(result.gpt_total)}</span>'
        f'<span class="score-pill">{gpt_r.latency_ms:.0f}ms</span>'
        f'<span class="score-pill">{gpt_r.word_count}w</span>'
    )

    nem_text = html.escape(nem_r.raw_text or nem_r.error or "(no response)")
    gpt_text = html.escape(gpt_r.raw_text or gpt_r.error or "(no response)")

    original_code = ""
    if bug.code_snippet.strip():
        original_code = (
            '<div class="original-bug">'
            '<h3>Original Code Snippet</h3>'
            f'<pre>{html.escape(bug.code_snippet.strip())}</pre>'
            '</div>'
        )

    diff_html = _render_diff(
        nem_r.raw_text or nem_r.error or "",
        gpt_r.raw_text or gpt_r.error or "",
    )

    url_link = f'<a href="{html.escape(bug.url)}" target="_blank">↗ source</a>' if not bug.url.startswith("seed://") else ""

    return f"""
<div class="bug-card">
  <div class="bug-header">
    <span class="bug-title"><strong>#{index + 1}</strong> {html.escape(bug.title)} {url_link}</span>
    <span class="category-badge">{html.escape(bug.category)}</span>
    <span class="winner-badge {winner_class}">{winner_text}</span>
    <span class="chevron">▼</span>
  </div>
  <div class="bug-body">
    {original_code}
    <div class="side-by-side">
      <div class="model-panel">
        <h3 style="color:var(--nem)">Nemotron Response</h3>
        <div class="scores-row">{nem_scores}</div>
        <pre style="margin-top:12px">{nem_text}</pre>
      </div>
      <div class="model-panel">
        <h3 style="color:var(--gpt)">GPT-Nano Response</h3>
        <div class="scores-row">{gpt_scores}</div>
        <pre style="margin-top:12px">{gpt_text}</pre>
      </div>
    </div>
    <div class="diff-section">
      <h3>Response Diff (Nemotron → GPT-Nano)</h3>
      {diff_html}
    </div>
  </div>
</div>
"""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(results: Sequence[EvalResult], output_path: str | None = None) -> str:
    """
    Render the HTML report and write it to *output_path*.
    Returns the path of the written file.
    """
    if output_path is None:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, config.REPORT_FILENAME)

    total = len(results)
    if total == 0:
        raise ValueError("No results to report")

    nem_wins = sum(1 for r in results if r.winner == "nemotron")
    gpt_wins = sum(1 for r in results if r.winner == "gpt")
    ties = total - nem_wins - gpt_wins

    nem_avg = sum(r.nemotron_total for r in results) / total
    gpt_avg = sum(r.gpt_total for r in results) / total
    nem_lat = sum(r.nemotron_response.latency_ms for r in results) / total

    # Dimension breakdown
    dims = ["Compilability", "Correctness", "Verbosity", "Overall"]
    nem_dim = [
        sum(r.nemotron_compilable for r in results) / total,
        sum(r.nemotron_correctness for r in results) / total,
        sum(r.nemotron_verbosity for r in results) / total,
        nem_avg,
    ]
    gpt_dim = [
        sum(r.gpt_compilable for r in results) / total,
        sum(r.gpt_correctness for r in results) / total,
        sum(r.gpt_verbosity for r in results) / total,
        gpt_avg,
    ]

    chart_html = "".join(_bar(d, n, g) for d, n, g in zip(dims, nem_dim, gpt_dim))
    cards_html = "".join(_render_bug_card(r, i) for i, r in enumerate(results))

    # Derive model names from first result
    nem_model = results[0].nemotron_response.model_name if results else config.NEMOTRON_MODEL
    gpt_model = results[0].gpt_response.model_name if results else config.OPENAI_MODEL

    page = (
        _HTML_TEMPLATE
        .replace("{{ nemotron_model }}", html.escape(nem_model))
        .replace("{{ gpt_model }}", html.escape(gpt_model))
        .replace("{{ timestamp }}", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        .replace("{{ total_bugs }}", str(total))
        .replace("{{ nem_wins }}", str(nem_wins))
        .replace("{{ gpt_wins }}", str(gpt_wins))
        .replace("{{ ties }}", str(ties))
        .replace("{{ nem_avg_score }}", f"{nem_avg:.2f}")
        .replace("{{ gpt_avg_score }}", f"{gpt_avg:.2f}")
        .replace("{{ nem_avg_latency }}", f"{nem_lat:.0f}")
        .replace("{{ dimension_chart_html }}", chart_html)
        .replace("{{ bug_cards_html }}", cards_html)
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    return output_path


def save_json(results: Sequence[EvalResult], output_path: str | None = None) -> str:
    """Save raw results as JSON alongside the HTML report."""
    if output_path is None:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, "battle_results.json")

    data = [r.to_dict() for r in results]
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return output_path
