"""Value layer: why journeys matter for lifetime value.

Two honest outputs:
1. `journey_depth_vs_value` - DESCRIPTIVE. Do customers who bought into more
   than one need of their mission keep spending more afterwards? This is a
   correlation, not proof that targeting causes it. The causal test is the
   holdout experiment described in docs/experiment_design.md.
2. `next_need_opportunity` - a PRIORITISATION HEURISTIC, not a CLV model:
   sum over recommended needs of (relative likelihood x typical basket value).
   Use it to rank who to talk to first, not to forecast revenue.
"""
from __future__ import annotations

import pandas as pd

from .config import PipelineConfig


def need_prices(events: pd.DataFrame) -> pd.Series:
    buys = events[events["event_type"] == "purchase"]
    src = buys if len(buys) > 50 else events
    return src.groupby("need")["price"].median()


def journey_depth_vs_value(events: pd.DataFrame, missions: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    """Group buyers by how many needs of their primary mission they bought before
    the cutoff, then compare what they did in the following window."""
    cutoff = pd.Timestamp(cfg.cutoff)
    end = cutoff + pd.Timedelta(days=cfg.horizon_days)
    fut = events[(events["event_time"] >= cutoff) & (events["event_time"] < end) & (events["event_type"] == "purchase")]
    hist_buyers = events[(events["event_time"] < cutoff) & (events["event_type"] == "purchase")]["user_id"].unique()

    prim = missions[missions["is_primary"]].drop_duplicates("user_id").set_index("user_id")["needs_bought"]
    df = pd.DataFrame(index=pd.Index(hist_buyers, name="user_id"))
    df["mission_needs_bought"] = prim.reindex(df.index).fillna(0)

    def bucket(n: float) -> str:
        if n == 0:
            return "0 - bought outside any mission"
        if n == 1:
            return "1 need in mission"
        return "2+ needs in mission"

    df["group"] = df["mission_needs_bought"].map(bucket)
    spend = fut.groupby("user_id")["price"].sum()
    orders = fut.groupby("user_id")["user_session"].nunique()
    df["next_spend"] = spend.reindex(df.index).fillna(0)
    df["next_orders"] = orders.reindex(df.index).fillna(0)
    df["bought_again"] = df["next_orders"] > 0
    out = df.groupby("group").agg(
        customers=("next_spend", "size"),
        repeat_rate=("bought_again", "mean"),
        avg_next_spend=("next_spend", "mean"),
        avg_next_orders=("next_orders", "mean"),
    )
    return out.reset_index()


def next_need_opportunity(recs: pd.DataFrame, prices: pd.Series) -> pd.DataFrame:
    """recs: user_id, need, score (one row per recommended need)."""
    r = recs.copy()
    r["likelihood"] = r["score"] / r.groupby("user_id")["score"].transform("sum")
    r["typical_basket"] = r["need"].map(prices).fillna(prices.median())
    r["opportunity"] = r["likelihood"] * r["typical_basket"]
    return r.groupby("user_id").agg(next_need_opportunity=("opportunity", "sum")).reset_index()
