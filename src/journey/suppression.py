"""Stop showing the same ad again.

Two rules, both measurable:
1. Bought it -> stop advertising it (and its need) for a cooldown window.
   Show the next need instead.
2. Fatigued   -> viewed the same product many times, across several sessions,
   never added to cart. Another impression of the same ad is unlikely to
   change that. Swap to an alternative in the same need (different brand,
   similar price) or move to the next need.
"""
from __future__ import annotations

import pandas as pd

from .config import PipelineConfig


def suppression_list(events: pd.DataFrame, as_of: pd.Timestamp, cfg: PipelineConfig | None = None) -> pd.DataFrame:
    cfg = cfg or PipelineConfig()
    hist = events[events["event_time"] < as_of]

    bought = (
        hist[hist["event_type"] == "purchase"]
        .groupby(["user_id", "product_id", "need"])["event_time"].max().reset_index()
        .rename(columns={"event_time": "since"})
    )
    bought["reason"] = "bought"
    bought["suppress_until"] = bought["since"] + pd.Timedelta(days=cfg.purchase_cooldown_days)
    bought = bought[bought["suppress_until"] > as_of]

    per_prod = hist.assign(
        is_view=(hist["event_type"] == "view").astype(int),
        is_cart=(hist["event_type"] != "view").astype(int),
    ).groupby(["user_id", "product_id", "need"]).agg(
        views=("is_view", "sum"),
        carts=("is_cart", "sum"),
        sessions=("user_session", "nunique"),
        since=("event_time", "max"),
    ).reset_index()
    fatigued = per_prod[
        (per_prod["views"] >= cfg.fatigue_views) & (per_prod["sessions"] >= cfg.fatigue_sessions) & (per_prod["carts"] == 0)
    ].copy()
    fatigued["reason"] = "fatigued"
    fatigued["suppress_until"] = fatigued["since"] + pd.Timedelta(days=21)
    fatigued = fatigued[fatigued["suppress_until"] > as_of]  # only pauses still running

    cols = ["user_id", "product_id", "need", "reason", "since", "suppress_until"]
    return pd.concat([bought[cols], fatigued[cols]], ignore_index=True)


def alternatives(events: pd.DataFrame, product_id: int, n: int = 3) -> pd.DataFrame:
    """Same need, different brand, price within +/-30% - ranked by how often others bought it."""
    p = events.loc[events["product_id"] == product_id].iloc[0]
    same = events[(events["need"] == p["need"]) & (events["brand"] != p["brand"])]
    same = same[same["price"].between(p["price"] * 0.7, p["price"] * 1.3)]
    if same.empty:
        return pd.DataFrame(columns=["product_id", "brand", "price", "buyers"])
    g = same.groupby(["product_id", "brand"]).agg(
        price=("price", "median"), buyers=("event_type", lambda s: (s == "purchase").sum())
    ).reset_index()
    return g.sort_values(["buyers", "price"], ascending=[False, True]).head(n)


def retargeting_waste(events: pd.DataFrame, as_of: pd.Timestamp, last_n: int = 5) -> dict:
    """How much of a classic 'recently viewed products' retargeting pool is wasted?

    Classic setup: retarget each user's last N viewed products. We count slots
    pointing at products the user already bought.
    """
    hist = events[events["event_time"] < as_of]
    views = hist[hist["event_type"] == "view"].sort_values("event_time")
    last = views.drop_duplicates(["user_id", "product_id"], keep="last").groupby("user_id").tail(last_n)
    bought = set(map(tuple, hist.loc[hist["event_type"] == "purchase", ["user_id", "product_id"]].to_numpy()))
    bought_need = set(map(tuple, hist.loc[hist["event_type"] == "purchase", ["user_id", "need"]].to_numpy()))
    keys = list(zip(last["user_id"], last["product_id"]))
    need_keys = list(zip(last["user_id"], last["need"]))
    n = len(keys)
    return {
        "retarget_slots": n,
        "slots_already_bought_product": sum(k in bought for k in keys),
        "slots_need_already_bought": sum(k in bought_need for k in need_keys),
        "share_product_bought": sum(k in bought for k in keys) / n if n else 0.0,
        "share_need_bought": sum(k in bought_need for k in need_keys) / n if n else 0.0,
    }
