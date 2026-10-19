"""Next-need model: "customers who were here went there next".

We learn need-to-need transitions from the order in which customers *first*
engage with each need, then score what a customer is most likely to need next,
excluding what they have already looked at. It is deliberately simple and
fully explainable: every recommendation can be traced to "X% of people who
looked at a sofa went on to look at a bed".

Three models are compared on the same holdout so the improvement is measured,
not claimed:
    popularity          - most common new needs overall (what most ads do)
    transitions         - next-need transitions from this customer's history
    transitions+mission - transitions, boosted inside the detected life mission
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import EVENT_WEIGHTS, MISSIONS, PipelineConfig

MISSION_PREFIXES = {m.key: m.needs for m in MISSIONS}


def first_touches(events: pd.DataFrame) -> pd.DataFrame:
    """(user, need) -> first time engaged, strongest action, order index."""
    ft = (
        events.assign(w=events["event_type"].map(EVENT_WEIGHTS).astype(float))
        .groupby(["user_id", "need"])
        .agg(t=("event_time", "min"), strength=("w", "max"))
        .reset_index()
        .sort_values(["user_id", "t"])
    )
    ft["pos"] = ft.groupby("user_id").cumcount()
    return ft


def short_need(need: str) -> str:
    """'furniture.living_room.sofa' -> 'sofa'; 'kids.carriage' -> 'carriage'."""
    return need.split(".")[-1].replace("_", " ")


def home_mission(need: str) -> str | None:
    """The mission whose most specific prefix matches this need.
    A cradle matches both 'furniture.bedroom' (new home) and 'furniture.bedroom.cradle'
    (baby); the longer, more specific prefix wins."""
    best, best_len = None, -1
    for m, prefixes in MISSION_PREFIXES.items():
        for p in prefixes:
            if (need == p or need.startswith(p + ".")) and len(p) > best_len:
                best, best_len = m, len(p)
    return best


def need_in_mission(need: str, mission: str) -> bool:
    return any(need == p or need.startswith(p + ".") or p.startswith(need + ".") for p in MISSION_PREFIXES[mission])


@dataclass
class NextNeedModel:
    window: int = 3  # look up to 3 steps ahead in a journey
    transitions: pd.DataFrame | None = None  # from_need, to_need, weight, prob, support
    popularity: pd.Series | None = None

    def fit(self, events: pd.DataFrame) -> "NextNeedModel":
        ft = first_touches(events)
        a = ft[["user_id", "need", "pos"]]
        pairs = a.merge(a, on="user_id", suffixes=("_from", "_to"))
        gap = pairs["pos_to"] - pairs["pos_from"]
        pairs = pairs[(gap > 0) & (gap <= self.window)].assign(w=lambda d: 1.0 / (d["pos_to"] - d["pos_from"]))
        tr = (
            pairs.groupby(["need_from", "need_to"])
            .agg(weight=("w", "sum"), support=("user_id", "nunique"))
            .reset_index()
            .rename(columns={"need_from": "from_need", "need_to": "to_need"})
        )
        tr["prob"] = tr["weight"] / tr.groupby("from_need")["weight"].transform("sum")
        self.transitions = tr
        # popularity of a need as a *new* interest (excludes each user's first need)
        self.popularity = ft[ft["pos"] > 0]["need"].value_counts(normalize=True)
        return self

    # ------------------------------------------------------------------ scoring
    def recommend_batch(
        self,
        ft: pd.DataFrame,
        k: int = 5,
        user_missions: pd.DataFrame | None = None,
        mission_boost: float = 1.0,
        exclude: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Score next needs for many customers at once.

        ft            first_touches() rows for the customers to score
        user_missions (user_id, mission) rows - candidates inside these get boosted
        exclude       (user_id, need) rows never to recommend (e.g. already bought)
        Returns long table: user_id, need, score, why, rank.
        """
        if ft.empty:
            return pd.DataFrame(columns=["user_id", "need", "score", "why", "rank"])
        h = ft[["user_id", "need", "strength", "pos"]].copy()
        # recent and stronger actions count more
        h["w"] = h["strength"] * 0.7 ** (h.groupby("user_id")["pos"].transform("max") - h["pos"])
        c = h.merge(self.transitions, left_on="need", right_on="from_need")
        c["contrib"] = c["w"] * c["prob"]
        c = c.sort_values("contrib", ascending=False)
        scores = c.groupby(["user_id", "to_need"], sort=False).agg(
            score=("contrib", "sum"), from_need=("from_need", "first"), prob=("prob", "first")
        ).reset_index().rename(columns={"to_need": "need"})
        scores["why"] = (
            (scores["prob"] * 100).round(0).astype(int).astype(str) + "% of people who looked at "
            + scores["from_need"].map(short_need) + " went on to this"
        )

        # small popularity prior: fills gaps for thin histories, breaks ties
        users = pd.DataFrame({"user_id": h["user_id"].unique()})
        pop = self.popularity.head(40).rename("p").reset_index().rename(columns={"index": "need"})
        pop.columns = ["need", "p"]
        prior = users.merge(pop, how="cross")
        scores = prior.merge(scores[["user_id", "need", "score", "why"]], on=["user_id", "need"], how="outer")
        scores["score"] = scores["score"].fillna(0) + scores["p"].fillna(0) * 1e-3
        scores["why"] = scores["why"].fillna("Popular next step for shoppers like this")

        if user_missions is not None and len(user_missions) and mission_boost != 1.0:
            nm = need_mission_table(scores["need"].unique())
            boosted = scores[["user_id", "need"]].merge(nm, on="need").merge(user_missions[["user_id", "mission"]], on=["user_id", "mission"])
            key = pd.MultiIndex.from_frame(boosted[["user_id", "need"]].drop_duplicates())
            hit = pd.MultiIndex.from_frame(scores[["user_id", "need"]]).isin(key)
            scores.loc[hit, "score"] *= mission_boost

        drop = h[["user_id", "need"]]
        if exclude is not None and len(exclude):
            drop = pd.concat([drop, exclude[["user_id", "need"]]])
        drop_idx = pd.MultiIndex.from_frame(drop.drop_duplicates())
        scores = scores[~pd.MultiIndex.from_frame(scores[["user_id", "need"]]).isin(drop_idx)]

        scores = scores.sort_values(["user_id", "score"], ascending=[True, False])
        scores = scores.groupby("user_id").head(k).copy()
        scores["rank"] = scores.groupby("user_id").cumcount() + 1
        return scores[["user_id", "need", "score", "why", "rank"]].reset_index(drop=True)

    def recommend(self, user_ft: pd.DataFrame, k: int = 5, missions: list[str] | None = None,
                  mission_boost: float = 1.0, exclude: set[str] | None = None) -> pd.DataFrame:
        """Single-customer convenience wrapper (used by the app)."""
        uid = user_ft["user_id"].iloc[0]
        um = pd.DataFrame({"user_id": uid, "mission": missions or []})
        ex = pd.DataFrame({"user_id": uid, "need": sorted(exclude or [])})
        return self.recommend_batch(user_ft, k, um, mission_boost, ex)

    def popular_batch(self, ft: pd.DataFrame, k: int = 5) -> pd.DataFrame:
        users = pd.DataFrame({"user_id": ft["user_id"].unique()})
        pop = pd.DataFrame({"need": self.popularity.index[: k + 30], "p": self.popularity.to_numpy()[: k + 30]})
        c = users.merge(pop, how="cross")
        seen = pd.MultiIndex.from_frame(ft[["user_id", "need"]])
        c = c[~pd.MultiIndex.from_frame(c[["user_id", "need"]]).isin(seen)]
        return c.sort_values(["user_id", "p"], ascending=[True, False]).groupby("user_id").head(k)


def need_mission_table(needs) -> pd.DataFrame:
    rows = [(n, m) for n in needs for m in MISSION_PREFIXES if need_in_mission(n, m)]
    return pd.DataFrame(rows, columns=["need", "mission"])


# ---------------------------------------------------------------------- evaluation
def holdout_targets(events: pd.DataFrame, cutoff: pd.Timestamp, horizon_days: int) -> pd.DataFrame:
    """New needs each user engaged with (and purchased) in the window after cutoff."""
    hist = events[events["event_time"] < cutoff]
    fut = events[(events["event_time"] >= cutoff) & (events["event_time"] < cutoff + pd.Timedelta(days=horizon_days))]
    seen = hist.groupby("user_id")["need"].agg(set)
    fut = fut[fut["user_id"].isin(seen.index)]
    new_any = fut.groupby("user_id")["need"].agg(set)
    new_buy = fut[fut["event_type"] == "purchase"].groupby("user_id")["need"].agg(set)
    t = pd.DataFrame({"seen": seen.reindex(new_any.index), "future": new_any})
    t["new_needs"] = [f - s for f, s in zip(t["future"], t["seen"])]
    t["new_bought"] = [new_buy.get(u, set()) - s for u, s in zip(t.index, t["seen"])]
    return t[t["new_needs"].map(len) > 0]


def evaluate(events: pd.DataFrame, missions: pd.DataFrame, cfg: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on history before cutoff, test on what customers did next.

    Returns (summary by model x segment, per-user predictions for inspection).
    """
    cutoff = pd.Timestamp(cfg.cutoff)
    hist = events[events["event_time"] < cutoff]
    model = NextNeedModel().fit(hist)
    targets = holdout_targets(events, cutoff, cfg.horizon_days)
    ft = first_touches(hist)
    ft = ft[ft["user_id"].isin(targets.index)]
    um = missions[["user_id", "mission"]].drop_duplicates() if not missions.empty else pd.DataFrame(columns=["user_id", "mission"])
    preds = {
        "popularity": model.popular_batch(ft, cfg.top_k),
        "transitions": model.recommend_batch(ft, cfg.top_k),
        "transitions+mission": model.recommend_batch(ft, cfg.top_k, um, cfg.mission_boost),
    }
    in_mission = set(um["user_id"])
    rows = []
    for name, p in preds.items():
        lists = p.groupby("user_id")["need"].agg(list)
        for uid in targets.index.intersection(lists.index):
            truth, bought = targets.at[uid, "new_needs"], targets.at[uid, "new_bought"]
            pl = lists[uid]
            hits = len(set(pl) & truth)
            rows.append({
                "user_id": uid,
                "model": name,
                "segment": "in a mission" if uid in in_mission else "no mission",
                "hit": hits > 0,
                "recall": hits / len(truth),
                "buy_hit": (len(set(pl) & bought) > 0) if bought else np.nan,
                "n_true": len(truth),
                "pred": pl,
            })
    per_user = pd.DataFrame(rows)
    seg = pd.concat([per_user, per_user.assign(segment="all customers")])
    summary = (
        seg.groupby(["segment", "model"])
        .agg(users=("user_id", "nunique"), hit_rate=("hit", "mean"), recall=("recall", "mean"), purchase_hit_rate=("buy_hit", "mean"))
        .reset_index()
    )
    base = summary[summary["model"] == "popularity"].set_index("segment")["hit_rate"]
    summary["lift_vs_popularity"] = summary["hit_rate"] / summary["segment"].map(base)
    return summary, per_user
