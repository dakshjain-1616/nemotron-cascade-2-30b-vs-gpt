#!/usr/bin/env python3
"""Generate social-media infographics and animated GIF for the benchmark."""

import os
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.gridspec import GridSpec
import matplotlib.patheffects as pe
import imageio

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Colour palette ────────────────────────────────────────────────────────────
BG_DARK   = "#0d1117"
BG_CARD   = "#161b22"
BG_CARD2  = "#1c2128"
GPT_COL   = "#00e5a0"   # emerald-green
NEM_COL   = "#ff6b35"   # vivid orange
GOLD      = "#ffd700"
WHITE     = "#f0f6fc"
GREY      = "#8b949e"
GREY2     = "#30363d"
RED       = "#f85149"
BLUE      = "#58a6ff"

# ── Data ──────────────────────────────────────────────────────────────────────
BUGS = [
    "I2C Timing",
    "Memory\nCorruption",
    "Peripheral\nConflict",
    "Watchdog\nReset",
    "Interrupt\nConflict",
]
NEM_SCORES  = [0.455, 0.800, 0.520, 0.720, 0.500]
GPT_SCORES  = [0.560, 0.960, 0.940, 0.920, 0.920]

NEM_COMPILE = [0.10, 0.60, 0.10, 0.50, 0.10]
GPT_COMPILE = [0.10, 0.90, 0.90, 0.80, 0.80]

NEM_CORRECT = [0.962, 1.000, 1.000, 1.000, 1.000]
GPT_CORRECT = [1.000, 1.000, 1.000, 1.000, 1.000]

NEM_VERBOS  = [0.15, 0.80, 0.40, 0.60, 0.30]
GPT_VERBOS  = [0.60, 1.00, 0.90, 1.00, 1.00]

NEM_LATENCY = [7996,  6428,  10130, 9339,  11075]
GPT_LATENCY = [5912,  4373,  5911,  5483,  5370]

AVG = {
    "nem_total":   0.599,  "gpt_total":   0.860,
    "nem_compile": 0.280,  "gpt_compile": 0.700,
    "nem_correct": 0.992,  "gpt_correct": 1.000,
    "nem_verbos":  0.450,  "gpt_verbos":  0.900,
    "nem_latency": 8994,   "gpt_latency": 5410,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def set_dark_bg(fig):
    fig.patch.set_facecolor(BG_DARK)

def card_rect(ax, x, y, w, h, color=BG_CARD, radius=0.04, **kw):
    fancy = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=0, facecolor=color, **kw
    )
    ax.add_patch(fancy)
    return fancy

def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  saved → {path}")
    plt.close(fig)
    return path

def pct_bar(ax, y, value, color, max_val=1.0, height=0.06, xstart=0.0, width=0.6):
    """Draw a filled progress bar."""
    ax.add_patch(FancyBboxPatch(
        (xstart, y), width, height,
        boxstyle="round,pad=0,rounding_size=0.01",
        linewidth=0, facecolor=GREY2
    ))
    filled = width * (value / max_val)
    ax.add_patch(FancyBboxPatch(
        (xstart, y), filled, height,
        boxstyle="round,pad=0,rounding_size=0.01",
        linewidth=0, facecolor=color
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  HERO OVERVIEW  (1080 × 1080  ≈ Instagram square)
# ═══════════════════════════════════════════════════════════════════════════════
def make_hero():
    fig = plt.figure(figsize=(10.8, 10.8))
    set_dark_bg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")

    # — Background gradient panels —
    card_rect(ax, 0.03, 0.03, 0.94, 0.94, color=BG_CARD, radius=0.05)

    # — Top glow strip —
    for i in range(60):
        alpha = 0.07 * (1 - i / 60)
        ax.add_patch(plt.Rectangle((0, 0.88 - i * 0.003), 1, 0.003,
                                    color=GPT_COL, alpha=alpha, zorder=0))

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.text(0.5, 0.91, "AI MODEL BENCHMARK", ha="center", va="center",
            fontsize=13, color=GREY, fontweight="bold",
            fontfamily="DejaVu Sans", transform=ax.transAxes,
            zorder=5)
    ax.text(0.5, 0.84, "Nemotron 3 Super  vs  GPT-5.4 Nano",
            ha="center", va="center", fontsize=22, color=WHITE,
            fontweight="bold", fontfamily="DejaVu Sans", transform=ax.transAxes,
            zorder=5)
    ax.text(0.5, 0.795, "Real-world Arduino embedded debugging  ·  5 bugs  ·  OpenRouter API",
            ha="center", va="center", fontsize=10, color=GREY,
            fontfamily="DejaVu Sans", transform=ax.transAxes, zorder=5)

    # divider
    ax.plot([0.1, 0.9], [0.775, 0.775], color=GREY2, linewidth=1, zorder=5)

    # ── Big score cards ────────────────────────────────────────────────────────
    for xi, (label, score, col, sub) in enumerate([
        ("NEMOTRON\n3 SUPER 120B", "0.599", NEM_COL, "nvidia/nemotron-3-super-120b-a12b"),
        ("GPT-5.4\nNANO", "0.860", GPT_COL, "openai/gpt-5.4-nano"),
    ]):
        cx = 0.27 if xi == 0 else 0.73
        card_rect(ax, cx - 0.21, 0.53, 0.42, 0.21, color=BG_CARD2, radius=0.03)
        ax.text(cx, 0.70, label, ha="center", va="center", fontsize=13,
                color=col, fontweight="bold", transform=ax.transAxes, zorder=6)
        ax.text(cx, 0.60, score, ha="center", va="center", fontsize=40,
                color=col, fontweight="bold", transform=ax.transAxes, zorder=6)
        ax.text(cx, 0.54, "avg total score", ha="center", va="center",
                fontsize=9, color=GREY, transform=ax.transAxes, zorder=6)

    # VS badge
    circle = plt.Circle((0.5, 0.635), 0.045, color=BG_DARK, zorder=7)
    ax.add_patch(circle)
    ax.text(0.5, 0.635, "VS", ha="center", va="center", fontsize=14,
            color=WHITE, fontweight="bold", transform=ax.transAxes, zorder=8)

    # ── 4 metric bars ─────────────────────────────────────────────────────────
    metrics = [
        ("Compilability", AVG["nem_compile"], AVG["gpt_compile"]),
        ("Correctness",   AVG["nem_correct"], AVG["gpt_correct"]),
        ("Verbosity",     AVG["nem_verbos"],  AVG["gpt_verbos"]),
        ("Avg Speed",     1 - AVG["nem_latency"] / 12000,
                          1 - AVG["gpt_latency"] / 12000),
    ]
    labels_right = [
        ("28%", "70%"),
        ("99.2%", "100%"),
        ("45%", "90%"),
        ("8.99s", "5.41s"),
    ]

    for i, ((mname, nv, gv), (nl, gl)) in enumerate(zip(metrics, labels_right)):
        y = 0.44 - i * 0.10
        ax.text(0.05, y + 0.028, mname, color=WHITE, fontsize=11,
                fontweight="bold", transform=ax.transAxes, zorder=6)

        # Nemotron bar
        ax.add_patch(FancyBboxPatch(
            (0.05, y - 0.005), 0.38, 0.025,
            boxstyle="round,pad=0,rounding_size=0.005",
            linewidth=0, facecolor=GREY2, transform=ax.transAxes, zorder=5))
        ax.add_patch(FancyBboxPatch(
            (0.05, y - 0.005), 0.38 * nv, 0.025,
            boxstyle="round,pad=0,rounding_size=0.005",
            linewidth=0, facecolor=NEM_COL, alpha=0.85,
            transform=ax.transAxes, zorder=6))
        ax.text(0.44, y + 0.0085, nl, color=NEM_COL, fontsize=9,
                fontweight="bold", transform=ax.transAxes, zorder=7)

        # GPT bar
        ax.add_patch(FancyBboxPatch(
            (0.55, y - 0.005), 0.38, 0.025,
            boxstyle="round,pad=0,rounding_size=0.005",
            linewidth=0, facecolor=GREY2, transform=ax.transAxes, zorder=5))
        ax.add_patch(FancyBboxPatch(
            (0.55, y - 0.005), 0.38 * gv, 0.025,
            boxstyle="round,pad=0,rounding_size=0.005",
            linewidth=0, facecolor=GPT_COL, alpha=0.9,
            transform=ax.transAxes, zorder=6))
        ax.text(0.94, y + 0.0085, gl, color=GPT_COL, fontsize=9,
                fontweight="bold", ha="right", transform=ax.transAxes, zorder=7)

    # vertical divider between bars
    ax.plot([0.5, 0.5], [0.04, 0.47], color=GREY2, lw=1, zorder=4,
            transform=ax.transAxes)

    # ── Winner banner ─────────────────────────────────────────────────────────
    card_rect(ax, 0.15, 0.05, 0.70, 0.10, color=GPT_COL, radius=0.03)
    ax.text(0.5, 0.10, "** GPT-5.4 NANO WINS **  5 / 5 tests", ha="center",
            va="center", fontsize=16, color=BG_DARK, fontweight="bold",
            transform=ax.transAxes, zorder=9)

    # legend dots top right
    for j, (lbl, col) in enumerate(
            [("Nemotron 3 Super", NEM_COL), ("GPT-5.4 Nano", GPT_COL)]):
        ax.add_patch(plt.Circle((0.78 + j * 0.0, 0.765 - j * 0.028),
                                0.008, color=col, transform=ax.transAxes, zorder=9))
        ax.text(0.795 + j * 0.0, 0.765 - j * 0.028, lbl, color=col,
                fontsize=9, va="center", transform=ax.transAxes, zorder=9)

    return save(fig, "infographic_hero.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  METRICS BREAKDOWN  (1080 × 1080)
# ═══════════════════════════════════════════════════════════════════════════════
def make_metrics():
    fig, ax = plt.subplots(figsize=(10.8, 10.8))
    set_dark_bg(fig)
    ax.set_facecolor(BG_CARD)
    ax.spines[:].set_color(GREY2)
    ax.tick_params(colors=GREY)

    cats      = ["Compilability\n(40%)", "Correctness\n(40%)",
                 "Verbosity\n(20%)", "Latency\n(lower=better)"]
    nem_vals  = [AVG["nem_compile"], AVG["nem_correct"],
                 AVG["nem_verbos"], 1 - AVG["nem_latency"] / 12000]
    gpt_vals  = [AVG["gpt_compile"], AVG["gpt_correct"],
                 AVG["gpt_verbos"], 1 - AVG["gpt_latency"] / 12000]
    labels_n  = ["28%",  "99.2%", "45%",  "8.99 s"]
    labels_g  = ["70%",  "100%",  "90%",  "5.41 s"]

    x = np.arange(len(cats))
    w = 0.32

    bars_n = ax.bar(x - w/2, nem_vals, w, color=NEM_COL,
                    alpha=0.88, label="Nemotron 3 Super", zorder=3)
    bars_g = ax.bar(x + w/2, gpt_vals, w, color=GPT_COL,
                    alpha=0.88, label="GPT-5.4 Nano",    zorder=3)

    # value labels
    for bar, lbl in zip(bars_n, labels_n):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                lbl, ha="center", color=NEM_COL, fontsize=11, fontweight="bold")
    for bar, lbl in zip(bars_g, labels_g):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                lbl, ha="center", color=GPT_COL, fontsize=11, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=12, color=WHITE)
    ax.set_yticks([0, 0.25, 0.50, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"],
                       fontsize=10, color=GREY)
    ax.set_ylim(0, 1.22)
    ax.yaxis.grid(True, color=GREY2, linestyle="--", alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    ax.set_title("Metric-by-Metric Comparison\nNemotron 3 Super 120B  vs  GPT-5.4 Nano",
                 color=WHITE, fontsize=18, fontweight="bold", pad=20)
    ax.legend(fontsize=12, facecolor=BG_CARD2, edgecolor=GREY2,
              labelcolor=WHITE, loc="upper right")

    fig.tight_layout(pad=2)
    return save(fig, "infographic_metrics.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  PER-BUG BREAKDOWN  (1200 × 900)
# ═══════════════════════════════════════════════════════════════════════════════
def make_perbug():
    fig, axes = plt.subplots(1, 2, figsize=(12, 9))
    set_dark_bg(fig)
    fig.subplots_adjust(wspace=0.08, left=0.02, right=0.98, top=0.88, bottom=0.06)

    short_bugs = ["I2C\nTiming", "Memory\nCorruption", "Peripheral\nConflict",
                  "Watchdog\nReset", "Interrupt\nConflict"]
    y = np.arange(len(short_bugs))

    for ax in axes:
        ax.set_facecolor(BG_CARD)
        ax.spines[:].set_color(GREY2)
        ax.tick_params(colors=GREY)
        ax.xaxis.grid(True, color=GREY2, linestyle="--", alpha=0.5, zorder=0)
        ax.set_axisbelow(True)
        ax.set_xlim(0, 1.1)

    # Left: Nemotron
    ax = axes[0]
    bars = ax.barh(y, NEM_SCORES, 0.5, color=NEM_COL, alpha=0.85, zorder=3)
    for bar, sc in zip(bars, NEM_SCORES):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{sc:.2f}", va="center", color=NEM_COL,
                fontsize=12, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(short_bugs, color=WHITE, fontsize=11)
    ax.set_title("Nemotron 3 Super 120B", color=NEM_COL,
                 fontsize=14, fontweight="bold", pad=10)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", ".25", ".50", ".75", "1.0"], color=GREY)

    # Right: GPT
    ax = axes[1]
    bars = ax.barh(y, GPT_SCORES, 0.5, color=GPT_COL, alpha=0.85, zorder=3)
    for bar, sc in zip(bars, GPT_SCORES):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{sc:.2f}", va="center", color=GPT_COL,
                fontsize=12, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([], color=WHITE)
    ax.set_title("GPT-5.4 Nano", color=GPT_COL,
                 fontsize=14, fontweight="bold", pad=10)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", ".25", ".50", ".75", "1.0"], color=GREY)

    fig.suptitle("Per-Bug Score Breakdown · Arduino Embedded Debugging",
                 color=WHITE, fontsize=16, fontweight="bold", y=0.97)
    return save(fig, "infographic_perbug.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  SPEED vs QUALITY  scatter (1080 × 1080)
# ═══════════════════════════════════════════════════════════════════════════════
def make_scatter():
    fig, ax = plt.subplots(figsize=(10.8, 10.8))
    set_dark_bg(fig)
    ax.set_facecolor(BG_CARD)
    ax.spines[:].set_color(GREY2)
    ax.tick_params(colors=GREY)

    # glow halo
    for s, alpha in [(800, 0.05), (500, 0.08), (250, 0.12)]:
        ax.scatter([AVG["gpt_latency"]], [AVG["gpt_total"]], s=s,
                   color=GPT_COL, alpha=alpha, zorder=2)
        ax.scatter([AVG["nem_latency"]], [AVG["nem_total"]], s=s,
                   color=NEM_COL, alpha=alpha, zorder=2)

    # per-bug points (small)
    ax.scatter(GPT_LATENCY, GPT_SCORES, s=80, color=GPT_COL,
               alpha=0.55, zorder=3, marker="o")
    ax.scatter(NEM_LATENCY, NEM_SCORES, s=80, color=NEM_COL,
               alpha=0.55, zorder=3, marker="o")

    # avg points (large)
    ax.scatter([AVG["gpt_latency"]], [AVG["gpt_total"]], s=260,
               color=GPT_COL, zorder=5, edgecolors=WHITE, linewidths=1.5)
    ax.scatter([AVG["nem_latency"]], [AVG["nem_total"]], s=260,
               color=NEM_COL, zorder=5, edgecolors=WHITE, linewidths=1.5)

    # labels
    ax.annotate("GPT-5.4 Nano\n(avg)", (AVG["gpt_latency"], AVG["gpt_total"]),
                xytext=(AVG["gpt_latency"] + 300, AVG["gpt_total"] + 0.04),
                color=GPT_COL, fontsize=12, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=GPT_COL, lw=1.5))
    ax.annotate("Nemotron 3 Super\n(avg)", (AVG["nem_latency"], AVG["nem_total"]),
                xytext=(AVG["nem_latency"] - 2200, AVG["nem_total"] - 0.09),
                color=NEM_COL, fontsize=12, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=NEM_COL, lw=1.5))

    ax.set_xlabel("Response Latency (ms)  ← faster", color=WHITE,
                  fontsize=13, labelpad=10)
    ax.set_ylabel("Total Score  (higher = better) →", color=WHITE,
                  fontsize=13, labelpad=10)
    ax.set_title("Speed vs Quality Trade-off\nNemotron 3 Super 120B  vs  GPT-5.4 Nano",
                 color=WHITE, fontsize=16, fontweight="bold", pad=14)

    ax.set_xlim(3500, 13000)
    ax.set_ylim(0.3, 1.15)
    ax.xaxis.grid(True, color=GREY2, linestyle="--", alpha=0.5)
    ax.yaxis.grid(True, color=GREY2, linestyle="--", alpha=0.5)
    ax.invert_xaxis()

    # ideal zone
    ax.add_patch(FancyBboxPatch(
        (4000, 0.85), 3000, 0.25,
        boxstyle="round,pad=0,rounding_size=200",
        linewidth=1.5, edgecolor=GPT_COL, facecolor=GPT_COL,
        alpha=0.06, transform=ax.transData, zorder=1))
    ax.text(5500, 1.06, "← ideal zone", color=GPT_COL,
            fontsize=10, alpha=0.7, ha="center")

    fig.tight_layout(pad=2.5)
    return save(fig, "infographic_scatter.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  SCORECARD / SUMMARY CARD  (1080 × 566  landscape — Twitter / LinkedIn)
# ═══════════════════════════════════════════════════════════════════════════════
def make_scorecard():
    fig = plt.figure(figsize=(10.8, 5.66))
    set_dark_bg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")

    # Background card
    card_rect(ax, 0.02, 0.04, 0.96, 0.92, color=BG_CARD, radius=0.04)

    # Title strip
    card_rect(ax, 0.02, 0.81, 0.96, 0.15, color=BG_CARD2, radius=0.04)
    ax.text(0.5, 0.89, "⚡ LLM SHOWDOWN  ·  Arduino Embedded Debugging  ·  5 Real Bugs",
            ha="center", va="center", fontsize=11, color=GREY,
            transform=ax.transAxes, zorder=5)
    ax.text(0.5, 0.84, "NEMOTRON 3 SUPER  vs  GPT-5.4 NANO",
            ha="center", va="center", fontsize=17, color=WHITE,
            fontweight="bold", transform=ax.transAxes, zorder=5)

    # Stat boxes
    stats = [
        ("WIN RATE",       "0 / 5",     "5 / 5"),
        ("TOTAL SCORE",    "0.599",      "0.860"),
        ("COMPILABILITY",  "28%",        "70%"),
        ("CORRECTNESS",    "99.2%",      "100%"),
        ("VERBOSITY",      "45%",        "90%"),
        ("AVG LATENCY",    "8.99 s",     "5.41 s"),
    ]
    col_xs = [0.065, 0.235, 0.41, 0.58, 0.745, 0.905]
    for j, (title, nv, gv) in enumerate(stats):
        cx = col_xs[j]
        card_rect(ax, cx - 0.075, 0.08, 0.15, 0.69, color=BG_CARD2, radius=0.02)
        ax.text(cx, 0.73, title, ha="center", va="center", fontsize=7.5,
                color=GREY, fontweight="bold", transform=ax.transAxes, zorder=6)
        ax.text(cx, 0.58, nv, ha="center", va="center", fontsize=14,
                color=NEM_COL, fontweight="bold", transform=ax.transAxes, zorder=6)
        ax.text(cx, 0.37, nv.replace(nv, "▲" if gv > nv else "▼"),
                ha="center", va="center", fontsize=8, color=GREY,
                transform=ax.transAxes, zorder=6)
        ax.text(cx, 0.22, gv, ha="center", va="center", fontsize=14,
                color=GPT_COL, fontweight="bold", transform=ax.transAxes, zorder=6)

    # Model name headers
    ax.text(0.5, 0.68, "NEMOTRON", ha="center", color=NEM_COL,
            fontsize=8, fontweight="bold", transform=ax.transAxes, zorder=7,
            alpha=0.7)
    ax.text(0.5, 0.20, "GPT-5.4 NANO", ha="center", color=GPT_COL,
            fontsize=8, fontweight="bold", transform=ax.transAxes, zorder=7,
            alpha=0.7)

    # Winner ribbon at right
    card_rect(ax, 0.76, 0.085, 0.22, 0.67, color=GPT_COL, radius=0.02)
    ax.text(0.87, 0.59, "WIN", ha="center", va="center",
            fontsize=16, color=BG_DARK, fontweight="bold",
            transform=ax.transAxes, zorder=8)
    ax.text(0.87, 0.42, "WINNER", ha="center", va="center", fontsize=14,
            color=BG_DARK, fontweight="bold", transform=ax.transAxes, zorder=8)
    ax.text(0.87, 0.32, "GPT-5.4", ha="center", va="center", fontsize=12,
            color=BG_DARK, fontweight="bold", transform=ax.transAxes, zorder=8)
    ax.text(0.87, 0.23, "NANO", ha="center", va="center", fontsize=12,
            color=BG_DARK, fontweight="bold", transform=ax.transAxes, zorder=8)
    ax.text(0.87, 0.12, "5 / 5 tests", ha="center", va="center", fontsize=9,
            color=BG_DARK, transform=ax.transAxes, zorder=8)

    return save(fig, "infographic_scorecard.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  ANIMATED GIF
# ═══════════════════════════════════════════════════════════════════════════════
def make_gif():
    import io
    from PIL import Image as PILImage
    import imageio.v2 as iio2

    frames = []

    def fig_to_pil(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        img = PILImage.open(buf).copy()   # copy out of BytesIO before closing
        plt.close(fig)
        return img

    def frame_fig(title, nem, gpt, metric_label, val_fmt=".0%"):
        fig = plt.figure(figsize=(8, 4.5))
        set_dark_bg(fig)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.axis("off")

        card_rect(ax, 0.02, 0.02, 0.96, 0.96, color=BG_CARD, radius=0.04)
        ax.text(0.5, 0.88, title, ha="center", va="center", fontsize=14,
                color=WHITE, fontweight="bold", transform=ax.transAxes)
        ax.text(0.5, 0.78, "Nemotron 3 Super  vs  GPT-5.4 Nano",
                ha="center", va="center", fontsize=10, color=GREY,
                transform=ax.transAxes)

        bar_w = 0.35
        # Nemotron bar
        ax.add_patch(FancyBboxPatch(
            (0.08, 0.35), bar_w, 0.22,
            boxstyle="round,pad=0,rounding_size=0.01",
            linewidth=0, facecolor=GREY2, transform=ax.transAxes))
        ax.add_patch(FancyBboxPatch(
            (0.08, 0.35), bar_w * nem, 0.22,
            boxstyle="round,pad=0,rounding_size=0.01",
            linewidth=0, facecolor=NEM_COL, alpha=0.85, transform=ax.transAxes))
        ax.text(0.255, 0.46, format(nem, val_fmt), ha="center", va="center",
                fontsize=18, color=BG_DARK, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.255, 0.28, "Nemotron 3 Super", ha="center", color=NEM_COL,
                fontsize=10, fontweight="bold", transform=ax.transAxes)

        # GPT bar
        ax.add_patch(FancyBboxPatch(
            (0.57, 0.35), bar_w, 0.22,
            boxstyle="round,pad=0,rounding_size=0.01",
            linewidth=0, facecolor=GREY2, transform=ax.transAxes))
        ax.add_patch(FancyBboxPatch(
            (0.57, 0.35), bar_w * gpt, 0.22,
            boxstyle="round,pad=0,rounding_size=0.01",
            linewidth=0, facecolor=GPT_COL, alpha=0.9, transform=ax.transAxes))
        ax.text(0.755, 0.46, format(gpt, val_fmt), ha="center", va="center",
                fontsize=18, color=BG_DARK, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.755, 0.28, "GPT-5.4 Nano", ha="center", color=GPT_COL,
                fontsize=10, fontweight="bold", transform=ax.transAxes)

        ax.text(0.5, 0.14, metric_label, ha="center", color=GREY,
                fontsize=9, transform=ax.transAxes)

        return fig_to_pil(fig)

    slides = [
        ("OVERALL SCORE",      AVG["nem_total"],    AVG["gpt_total"],
         "Weighted score: 40% compilability · 40% correctness · 20% verbosity"),
        ("COMPILABILITY",      AVG["nem_compile"],  AVG["gpt_compile"],
         "Does the response include complete, compilable Arduino sketches?"),
        ("CORRECTNESS",        AVG["nem_correct"],  AVG["gpt_correct"],
         "Does it correctly identify the root cause for each bug category?"),
        ("VERBOSITY / FORMAT", AVG["nem_verbos"],   AVG["gpt_verbos"],
         "Structured sections, code blocks, testing recommendations, word count"),
    ]

    # Each metric slide held for 3 frames (1.5 s @ 2 fps)
    for title, nv, gv, sub in slides:
        pil_img = frame_fig(title, nv, gv, sub)
        for _ in range(3):
            frames.append(np.array(pil_img))

    # Speed slide
    pil_speed = frame_fig(
        "RESPONSE SPEED",
        1 - AVG["nem_latency"] / 12000,
        1 - AVG["gpt_latency"] / 12000,
        f"Avg latency — Nemotron: {AVG['nem_latency']:.0f} ms  |  GPT: {AVG['gpt_latency']:.0f} ms")
    for _ in range(3):
        frames.append(np.array(pil_speed))

    # Winner frame
    fig = plt.figure(figsize=(8, 4.5))
    set_dark_bg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    card_rect(ax, 0.1, 0.15, 0.80, 0.70, color=GPT_COL, radius=0.05)
    ax.text(0.5, 0.72, "WINNER", ha="center", va="center",
            fontsize=32, color=BG_DARK, fontweight="bold", transform=ax.transAxes)
    ax.text(0.5, 0.56, "GPT-5.4 Nano", ha="center", va="center",
            fontsize=26, color=BG_DARK, fontweight="bold", transform=ax.transAxes)
    ax.text(0.5, 0.43, "5 / 5 tests  +  +43.6% overall score",
            ha="center", va="center", fontsize=14, color=BG_DARK,
            transform=ax.transAxes)
    ax.text(0.5, 0.30, "2.5x better compilability  |  40% faster",
            ha="center", va="center", fontsize=12, color=BG_DARK,
            transform=ax.transAxes)
    winner_pil = fig_to_pil(fig)
    for _ in range(5):
        frames.append(np.array(winner_pil))

    path = os.path.join(OUTPUT_DIR, "benchmark_animation.gif")
    iio2.mimsave(path, frames, fps=2, loop=0)
    print(f"  saved → {path}")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  LATENCY COMPARISON  (1080 × 600)
# ═══════════════════════════════════════════════════════════════════════════════
def make_latency():
    fig, ax = plt.subplots(figsize=(12, 6))
    set_dark_bg(fig)
    ax.set_facecolor(BG_CARD)
    ax.spines[:].set_color(GREY2)
    ax.tick_params(colors=GREY)

    short = ["I2C\nTiming", "Memory\nCorruption", "Peripheral\nConflict",
             "Watchdog\nReset", "Interrupt\nConflict"]
    x = np.arange(len(short))
    w = 0.33

    bars_n = ax.bar(x - w/2, NEM_LATENCY, w, color=NEM_COL,
                    alpha=0.85, label="Nemotron 3 Super")
    bars_g = ax.bar(x + w/2, GPT_LATENCY, w, color=GPT_COL,
                    alpha=0.85, label="GPT-5.4 Nano")

    for bar in bars_n:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 100,
                f"{bar.get_height()/1000:.1f}s", ha="center",
                color=NEM_COL, fontsize=9, fontweight="bold")
    for bar in bars_g:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 100,
                f"{bar.get_height()/1000:.1f}s", ha="center",
                color=GPT_COL, fontsize=9, fontweight="bold")

    ax.axhline(AVG["nem_latency"], color=NEM_COL, linestyle="--",
               alpha=0.5, linewidth=1.5, label=f"Nem avg {AVG['nem_latency']:.0f} ms")
    ax.axhline(AVG["gpt_latency"], color=GPT_COL, linestyle="--",
               alpha=0.5, linewidth=1.5, label=f"GPT avg {AVG['gpt_latency']:.0f} ms")

    ax.set_xticks(x)
    ax.set_xticklabels(short, color=WHITE, fontsize=11)
    ax.set_ylabel("Latency (ms)  ← lower is better", color=WHITE, fontsize=12)
    ax.set_title("Response Latency per Bug\nNemotron 3 Super 120B  vs  GPT-5.4 Nano",
                 color=WHITE, fontsize=15, fontweight="bold", pad=12)
    ax.yaxis.grid(True, color=GREY2, linestyle="--", alpha=0.5)
    ax.set_ylim(0, 13000)
    ax.legend(fontsize=10, facecolor=BG_CARD2, edgecolor=GREY2,
              labelcolor=WHITE)
    fig.tight_layout(pad=2)
    return save(fig, "infographic_latency.png")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating infographics …")
    make_hero()
    make_metrics()
    make_perbug()
    make_scatter()
    make_scorecard()
    make_latency()
    print("Generating animation …")
    make_gif()
    print("\nAll assets written to output/")
