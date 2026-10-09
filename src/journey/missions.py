"""Mission detection + journey stage.

Step 1  Which life event is this customer in?   (mission)
Step 2  How far along are they?                  (stage)

A mission is detected from *breadth* across related needs, not from volume in
one category. Ten views of one sofa = a sofa shopper. A sofa, a bed and a
fridge inside three weeks = somebody setting up a home, who will need curtains,
a vacuum and a drill next.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import EVENT_WEIGHTS, MISSIONS, PipelineConfig

STAGE_ORDER = [
    "Exploring",
    "Researching",
    "Ready to buy",
    "Next need",
    "Mission complete",
    "Gone quiet",
]

STAGE_RULES = {
    "Exploring": "Touched 2+ needs in the mission, few sessions, nothing in cart yet",
    "Researching": "Comparing across several sessions, products and brands",
    "Ready to buy": "Open cart in the mission from the last 14 days, not yet bought",
    "Next need": "Bought at least one thing in the mission — the journey is still open",
    "Mission complete": "Bought across most of the mission — move to loyalty, not acquisition",
    "Gone quiet": "No mission activity for 14+ days without completing it",
}


def tag_missions(events: pd.DataFrame) -> pd.DataFrame:
    """Attach mission key(s) to each event. One event can belong to 2 missions
    (a TV cabinet is both 'new home' and 'entertainment')."""
    codes = pd.Series(events["category_code"].unique(), name="category_code")
    rows = []
    for m in MISSIONS:
        hit = codes[codes.apply(lambda c, m=m: any(c == p or c.startswith(p + ".") for p in m.needs))]
        rows.append(pd.DataFrame({"category_code": hit.values, "mission": m.key}))
    lookup = pd.concat(rows, ignore_index=True)
    return events.merge(lookup, on="category_code", how="inner")


def _open_carts(ev: pd.DataFrame) -> pd.DataFrame:
    """Carted products with no later purchase of the same product."""
    carts = ev[ev["event_type"] == "cart"].groupby(["user_id", "mission", "product_id"])["event_time"].max()
    buys = ev[ev["event_type"] == "purchase"].groupby(["user_id", "mission", "product_id"])["event_time"].max()
    j = carts.to_frame("cart_t").join(buys.to_frame("buy_t"), how="left")
    open_ = j[j["buy_t"].isna() | (j["buy_t"] < j["cart_t"])].reset_index()
    return open_.groupby(["user_id", "mission"]).agg(open_carts=("product_id", "nunique"), last_cart=("cart_t", "max"))


def score_missions(events: pd.DataFrame, as_of: pd.Timestamp, cfg: PipelineConfig | None = None) -> pd.DataFrame:
    """One row per (user, mission) with score, breadth, stage. Only qualifying missions."""
    cfg = cfg or PipelineConfig()
    hist = events[events["event_time"] < as_of]
    ev = tag_missions(hist)
    if ev.empty:
        return pd.DataFrame()
    age = (as_of - ev["event_time"]).dt.total_seconds() / 86400
    ev = ev.assign(
        w=ev["event_type"].map(EVENT_WEIGHTS).astype(float) * np.power(0.5, age / cfg.recency_half_life_days)
    )
    g = ev.groupby(["user_id", "mission"])
    out = g.agg(
        score=("w", "sum"),
        needs_touched=("need", "nunique"),
        sessions=("user_session", "nunique"),
        products_viewed=("product_id", "nunique"),
        brands_viewed=("brand", "nunique"),
        first_seen=("event_time", "min"),
        last_seen=("event_time", "max"),
    )
    bought = ev[ev["event_type"] == "purchase"].groupby(["user_id", "mission"]).agg(
        needs_bought=("need", "nunique"), mission_spend=("price", "sum")
    )
    out = out.join(bought, how="left").join(_open_carts(ev), how="left")
    out[["needs_bought", "mission_spend", "open_carts"]] = out[["needs_bought", "mission_spend", "open_carts"]].fillna(0)

    min_needs = pd.Series({m.key: m.min_needs for m in MISSIONS})
    mn = min_needs.reindex(out.index.get_level_values("mission")).to_numpy()
    out = out[(out["needs_touched"].to_numpy() >= mn) & (out["score"] >= cfg.mission_min_score)].copy()

    out["days_since_active"] = (as_of - out["last_seen"]).dt.total_seconds() / 86400
    out["days_since_cart"] = (as_of - out["last_cart"]).dt.total_seconds() / 86400
    out["stage"] = assign_stage(out, cfg)
    out["is_primary"] = out.groupby(level="user_id")["score"].transform("max") == out["score"]
    return out.reset_index()


def assign_stage(m: pd.DataFrame, cfg: PipelineConfig) -> pd.Series:
    conds = [
        m["needs_bought"] >= cfg.complete_needs,
        m["days_since_active"] > cfg.gone_quiet_days,
        (m["open_carts"] > 0) & (m["days_since_cart"] <= cfg.open_cart_days),
        m["needs_bought"] >= 1,
        m["sessions"] >= cfg.research_sessions,
    ]
    choices = ["Mission complete", "Gone quiet", "Ready to buy", "Next need", "Researching"]
    return pd.Series(np.select(conds, choices, default="Exploring"), index=m.index)


def primary_missions(missions: pd.DataFrame) -> pd.DataFrame:
    return missions[missions["is_primary"]].drop_duplicates("user_id")
