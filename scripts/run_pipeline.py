"""Run the whole system end to end.

    python scripts/run_pipeline.py --demo        # demo data, ~30 seconds
    python scripts/run_pipeline.py               # real REES46 files in data/raw/
    python scripts/run_pipeline.py --sample 50   # keep 1 in 50 users (faster)

Writes to outputs/:
    evaluation.csv            next-need model vs popularity, by segment
    transitions.csv           learned need -> next need transitions
    missions_now.csv          every (customer, mission) with score and stage
    customer_actions.csv      one decision per active customer
    showcase.json             one example customer per use case (used by the app)
    recommendations.csv       top-k next needs per customer, with the reason
    suppression.csv           products to stop advertising, and why
    journey_depth_value.csv   mission depth vs what customers did next
    results.md                headline numbers, ready to paste into a write-up
    charts/*.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from journey import charts  # noqa: E402
from journey.actions import build_customer_actions  # noqa: E402
from journey.config import OUTPUTS, PipelineConfig  # noqa: E402
from journey.data_loader import load_events  # noqa: E402
from journey.missions import score_missions  # noqa: E402
from journey.next_need import NextNeedModel, evaluate  # noqa: E402
from journey.showcase import build_showcase  # noqa: E402
from journey.suppression import retargeting_waste  # noqa: E402
from journey.value import journey_depth_vs_value, need_prices, next_need_opportunity  # noqa: E402


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use data/raw/demo_events.csv.gz")
    ap.add_argument("--sample", type=int, default=20, help="keep 1 in N users from the real files")
    ap.add_argument("--refresh", action="store_true", help="re-read raw files, ignore cache")
    args = ap.parse_args()

    t0 = time.time()
    cfg = PipelineConfig(user_sample_mod=args.sample)
    source = "Demo data (REES46 schema, simulated)" if args.demo else f"REES46 multi-category store, Oct-Nov 2019, 1 in {args.sample} users"
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    events = load_events(cfg, demo=args.demo, refresh=args.refresh)
    log(f"events: {len(events):,} | customers: {events.user_id.nunique():,} | needs: {events.need.nunique()}", t0)

    # 1. Backtest: what we knew on the cutoff date vs what customers did next
    cutoff = pd.Timestamp(cfg.cutoff)
    missions_at_cutoff = score_missions(events, cutoff, cfg)
    summary, per_user = evaluate(events, missions_at_cutoff, cfg)
    summary.to_csv(OUTPUTS / "evaluation.csv", index=False)
    log("backtest done", t0)
    depth = journey_depth_vs_value(events, missions_at_cutoff, cfg)
    depth.to_csv(OUTPUTS / "journey_depth_value.csv", index=False)
    waste = retargeting_waste(events, cutoff)

    # 2. Today's view: everything we know up to the end of the data
    now = events["event_time"].max() + pd.Timedelta(seconds=1)
    model = NextNeedModel().fit(events)
    model.transitions.sort_values("weight", ascending=False).to_csv(OUTPUTS / "transitions.csv", index=False)
    missions_now = score_missions(events, now, cfg)
    missions_now.to_csv(OUTPUTS / "missions_now.csv", index=False)
    actions, recs, supp = build_customer_actions(events, missions_now, now, cfg, model)
    opp = next_need_opportunity(recs, need_prices(events))
    actions = actions.merge(opp, on="user_id", how="left")
    actions.to_csv(OUTPUTS / "customer_actions.csv", index=False)
    recs.to_csv(OUTPUTS / "recommendations.csv", index=False)
    supp.to_csv(OUTPUTS / "suppression.csv", index=False)
    log(f"decisions for {len(actions):,} active customers", t0)
    build_showcase(events, actions, missions_now, recs, supp, OUTPUTS / "showcase.json")

    # 3. Charts + results file
    charts.model_comparison(summary, source, cfg.top_k)
    charts.stage_mix(actions, source)
    charts.top_transitions(model.transitions, source, min_support=max(10, events.user_id.nunique() // 500))
    charts.retargeting_waste(waste, source)
    charts.depth_vs_value(depth, source)
    write_results(summary, actions, missions_now, waste, depth, model, source, cfg, args.demo)
    (OUTPUTS / "run_meta.json").write_text(json.dumps({"source": source, "demo": args.demo, "cutoff": cfg.cutoff}, indent=2))
    log("charts + results.md written to outputs/", t0)


def write_results(summary, actions, missions_now, waste, depth, model, source, cfg, demo) -> None:
    s = summary.set_index(["segment", "model"])

    def g(seg, model, col="hit_rate"):
        return s.loc[(seg, model), col]

    mission_share = (actions["stage"] != "No mission").mean()
    stage = actions[actions["stage"] != "No mission"]["stage"].value_counts(normalize=True)
    top = model.transitions[model.transitions["support"] >= 30].sort_values("prob", ascending=False).head(5)
    d = depth.set_index("group")
    banner = (
        "> **DEMO DATA — these numbers prove the code runs, not a business claim.**\n"
        "> Re-run without `--demo` on the real REES46 files before publishing any number.\n\n"
        if demo else ""
    )
    lines = [
        "# Results",
        "",
        banner + f"Source: **{source}** · cutoff {cfg.cutoff} · horizon {cfg.horizon_days} days · top-{cfg.top_k}",
        "",
        "## Next-need prediction (backtest)",
        "",
        "| Segment | Show what's popular | Predict next need | Lift | + mission boost |",
        "|---|---|---|---|---|",
    ]
    for seg in ["all customers", "in a mission", "no mission"]:
        lines.append(
            f"| {seg} | {g(seg, 'popularity'):.1%} | {g(seg, 'transitions'):.1%} | "
            f"{g(seg, 'transitions') / g(seg, 'popularity'):.2f}x | {g(seg, 'transitions+mission'):.1%} |"
        )
    lines += [
        "",
        f"Purchase hit rate (next new need *bought* was in the top {cfg.top_k}): popularity "
        f"{g('all customers', 'popularity', 'purchase_hit_rate'):.1%} vs next-need model "
        f"{g('all customers', 'transitions', 'purchase_hit_rate'):.1%}.",
        f"Customers evaluated: {int(g('all customers', 'transitions', 'users')):,}.",
        "",
        "## Where customers are right now",
        "",
        f"- {mission_share:.0%} of active customers show a life-mission pattern.",
    ]
    lines += [f"- {k}: {v:.0%} of mission customers" for k, v in stage.items()]
    lines += ["", "Missions detected (primary):", ""]
    lines += [f"- {k}: {v:,}" for k, v in actions["mission_name"].value_counts().items() if k != "—"]
    lines += [
        "",
        "## Wasted retargeting",
        "",
        f"- {waste['share_product_bought']:.1%} of 'last 5 viewed' retargeting slots point at a product the customer already bought.",
        f"- {waste['share_need_bought']:.1%} point at a need (e.g. 'a fridge') the customer already bought.",
        "",
        "## Strongest next-need transitions",
        "",
    ]
    lines += [f"- {r.from_need} → {r.to_need}: {r.prob:.0%} (n={r.support:,})" for r in top.itertuples()]
    lines += ["", "## Mission depth vs next-month behaviour (correlation, not causation)", ""]
    lines += [f"- {grp}: repeat rate {row.repeat_rate:.0%}, avg next-month spend {row.avg_next_spend:,.0f}" for grp, row in d.iterrows()]
    (OUTPUTS / "results.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
