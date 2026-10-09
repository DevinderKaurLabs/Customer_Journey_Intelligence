"""Static charts for the README / article, in the portfolio palette.

One idea per chart: the highlighted bar is navy, context is sky blue, and
every bar carries a direct value label so colour is never the only cue.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import CHARTS, MISSIONS, PALETTE  # noqa: E402
from .missions import STAGE_ORDER  # noqa: E402

NAVY, TEAL, SKY, BEIGE, MUTED = PALETTE["navy"], PALETTE["teal"], PALETTE["sky"], PALETTE["beige"], PALETTE["muted"]
INK, INK_2 = "#1F2B38", "#5B6B7C"
MISSION_NAMES = {m.key: m.name for m in MISSIONS}


def _style(ax, title: str, subtitle: str | None = None):
    fig = ax.figure
    fig.patch.set_facecolor(BEIGE)
    ax.set_facecolor(BEIGE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#CFC7C0")
    ax.tick_params(colors=INK_2, length=0, labelsize=10)
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", color=INK, pad=28)
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes, fontsize=10.5, color=INK_2)


def _save(fig, name: str, source: str) -> Path:
    fig.text(0.01, 0.01, f"Source: {source} · Customer Journey Intelligence", fontsize=8, color=INK_2)
    CHARTS.mkdir(parents=True, exist_ok=True)
    path = CHARTS / name
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=BEIGE)
    plt.close(fig)
    return path


def model_comparison(summary: pd.DataFrame, source: str, k: int = 5) -> Path:
    """Hit rate @k: popularity vs next-need model, per segment."""
    seg_order = ["all customers", "in a mission", "no mission"]
    s = summary[summary["model"].isin(["popularity", "transitions"])]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    width, x = 0.36, range(len(seg_order))
    for i, (model, color, label) in enumerate([("popularity", SKY, "Show what's popular"), ("transitions", NAVY, "Predict the next need")]):
        vals = [s[(s.segment == seg) & (s.model == model)]["hit_rate"].iloc[0] for seg in seg_order]
        xs = [xx + (i - 0.5) * width for xx in x]
        ax.bar(xs, vals, width=width - 0.03, color=color, label=label)
        for xx, v in zip(xs, vals):
            ax.text(xx, v + 0.015, f"{v:.0%}", ha="center", color=INK, fontsize=10, fontweight="bold" if model == "transitions" else "normal")
    ax.set_xticks(list(x), [s.title() for s in seg_order])
    ax.set_yticks([])
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="upper right", fontsize=10, labelcolor=INK)
    _style(ax, "Predicting the next need beats showing what's popular",
           f"Share of customers whose next new category was in our top {k}, next 30 days")
    return _save(fig, "01_next_need_vs_popularity.png", source)


def stage_mix(actions: pd.DataFrame, source: str) -> Path:
    """Where mission customers sit right now, by stage."""
    a = actions[actions["stage"] != "No mission"]
    counts = a["stage"].value_counts().reindex(STAGE_ORDER).fillna(0)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    colors = [NAVY if st == "Next need" else (MUTED if st == "Gone quiet" else SKY) for st in counts.index]
    ax.barh(counts.index[::-1], counts.values[::-1], color=colors[::-1], height=0.62)
    for y, v in enumerate(counts.values[::-1]):
        ax.text(v + counts.max() * 0.01, y, f"{int(v):,}  ({v / counts.sum():.0%})", va="center", color=INK, fontsize=10)
    ax.set_xticks([])
    ax.set_xlim(0, counts.max() * 1.25)
    _style(ax, "Every customer in a life mission gets a different job",
           "Active customers in a detected mission, by journey stage")
    return _save(fig, "02_stage_mix.png", source)


def top_transitions(transitions: pd.DataFrame, source: str, n: int = 12, min_support: int = 30) -> Path:
    t = transitions[transitions["support"] >= min_support].sort_values("prob", ascending=False).head(n)
    short = lambda s: s.str.split(".").str[-2:].str.join(" ").str.replace("_", " ")  # noqa: E731
    labels = (short(t["from_need"]) + "  →  " + short(t["to_need"])).tolist()
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.barh(labels[::-1], t["prob"].to_numpy()[::-1], color=TEAL, height=0.62)
    for y, (p, sup) in enumerate(zip(t["prob"].to_numpy()[::-1], t["support"].to_numpy()[::-1])):
        ax.text(p + 0.005, y, f"{p:.0%}  (n={sup:,})", va="center", color=INK, fontsize=9.5)
    ax.set_xticks([])
    ax.set_xlim(0, t["prob"].max() * 1.3)
    _style(ax, "What people look at next", "Strongest next-need transitions (share of onward journeys)")
    return _save(fig, "03_top_transitions.png", source)


def retargeting_waste(waste: dict, source: str) -> Path:
    vals = [waste["share_product_bought"], waste["share_need_bought"]]
    labels = ["Exact product\nalready bought", "Same need\nalready bought"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(labels, vals, color=[NAVY, SKY], width=0.5)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", color=INK, fontsize=13, fontweight="bold")
    ax.set_yticks([])
    ax.set_ylim(0, max(vals) * 1.35 + 0.02)
    _style(ax, "Classic retargeting pays to show people what they already bought",
           f"Share of 'last 5 viewed products' retargeting slots ({waste['retarget_slots']:,} slots)")
    return _save(fig, "04_retargeting_waste.png", source)


def depth_vs_value(depth: pd.DataFrame, source: str) -> Path:
    order = ["0 - bought outside any mission", "1 need in mission", "2+ needs in mission"]
    d = depth.set_index("group").reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    colors = [SKY, TEAL, NAVY][: len(d)]
    ax.bar([g.replace(" - ", "\n") for g in d.index], d["repeat_rate"], color=colors, width=0.55)
    for i, v in enumerate(d["repeat_rate"]):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", color=INK, fontsize=12, fontweight="bold")
    ax.set_yticks([])
    ax.set_ylim(0, d["repeat_rate"].max() * 1.35)
    _style(ax, "Customers deeper into a mission come back more",
           "Bought again in the next 30 days, by mission depth before the cutoff (correlation, not causation)")
    return _save(fig, "05_depth_vs_repeat.png", source)
