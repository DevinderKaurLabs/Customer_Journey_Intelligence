"""Turn mission + stage + next need + suppression into one decision per customer.

The point is that each stage gets a *different job*, not a different discount.
"""
from __future__ import annotations

import pandas as pd

from .config import MISSIONS, PipelineConfig
from .next_need import NextNeedModel, first_touches
from .suppression import suppression_list

MISSION_NAMES = {m.key: m.name for m in MISSIONS}

PLAYBOOK = {
    "Exploring": {
        "job": "Inspire",
        "message": "Mission guide content (e.g. a 'first month in a new home' checklist), not product ads",
        "channel": "Social / content, onsite banners",
        "avoid": "Discounts — they haven't decided what they want yet",
    },
    "Researching": {
        "job": "Help them decide",
        "message": "Comparisons, reviews, sizing and delivery facts for the need they are researching",
        "channel": "Onsite modules, email with comparison",
        "avoid": "Pushing a new category before this one is solved",
    },
    "Ready to buy": {
        "job": "Remove friction",
        "message": "Cart reminder with delivery date, installation, instalments",
        "channel": "Email / push within 24h",
        "avoid": "Default discounts — test first whether they're needed",
    },
    "Next need": {
        "job": "Serve the next need",
        "message": "Show the predicted next need; stop advertising what they bought",
        "channel": "Retargeting swap, email, app home feed",
        "avoid": "Re-showing the purchased product",
    },
    "Mission complete": {
        "job": "Make them loyal",
        "message": "Care, accessories, services, membership, referral",
        "channel": "CRM / loyalty",
        "avoid": "Acquisition-style ads for things they already own",
    },
    "Gone quiet": {
        "job": "One smart win-back",
        "message": "One message on the most likely next need, then stop",
        "channel": "Email or one paid touch",
        "avoid": "Retargeting forever",
    },
    "No mission": {
        "job": "Product-level retargeting, with fatigue rules",
        "message": "Last viewed product or close alternatives",
        "channel": "Standard retargeting",
        "avoid": "Products already bought or fatigued",
    },
}


def build_customer_actions(
    events: pd.DataFrame,
    missions: pd.DataFrame,
    as_of: pd.Timestamp,
    cfg: PipelineConfig | None = None,
    model: NextNeedModel | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (customer_actions, recommendations_long, suppression)."""
    cfg = cfg or PipelineConfig()
    hist = events[events["event_time"] < as_of]
    model = model or NextNeedModel().fit(hist)
    supp = suppression_list(events, as_of, cfg)

    prim = missions[missions["is_primary"]].drop_duplicates("user_id").set_index("user_id") if not missions.empty else pd.DataFrame()

    ft = first_touches(hist)
    # Only score customers active in the last 60 days - nobody else needs a decision today.
    recent = hist.groupby("user_id")["event_time"].max()
    active = recent[recent >= as_of - pd.Timedelta(days=60)].index
    ft = ft[ft["user_id"].isin(active)]

    um = missions[["user_id", "mission"]].drop_duplicates() if not missions.empty else None
    ex = supp.loc[supp["reason"] == "bought", ["user_id", "need"]]
    recs_long = model.recommend_batch(ft, cfg.top_k, um, cfg.mission_boost, ex)
    top = recs_long.pivot(index="user_id", columns="rank", values="need")

    rows = []
    for uid in ft["user_id"].unique():
        if uid in prim.index:
            p = prim.loc[uid]
            stage, mission = p["stage"], p["mission"]
            score, needs_t, needs_b = p["score"], p["needs_touched"], p["needs_bought"]
        else:
            stage, mission, score, needs_t, needs_b = "No mission", None, 0.0, 0, 0
        play = PLAYBOOK[stage]
        nn = top.loc[uid] if uid in top.index else {}
        rows.append({
            "user_id": uid,
            "mission": mission,
            "mission_name": MISSION_NAMES.get(mission, "—"),
            "stage": stage,
            "mission_score": round(float(score), 2),
            "needs_touched": int(needs_t),
            "needs_bought": int(needs_b),
            "last_active": recent[uid],
            "next_need_1": nn.get(1),
            "next_need_2": nn.get(2),
            "next_need_3": nn.get(3),
            "job": play["job"],
            "message": play["message"],
            "channel": play["channel"],
            "avoid": play["avoid"],
        })
    actions = pd.DataFrame(rows)
    n_supp = supp.groupby("user_id").size()
    actions["suppressed_products"] = actions["user_id"].map(n_supp).fillna(0).astype(int)
    return actions, recs_long, supp
