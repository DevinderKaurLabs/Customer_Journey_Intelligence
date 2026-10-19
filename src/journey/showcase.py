"""Pick one clear example customer for each thing the system does.

Used by the app ("See it in action" on Home) and by anyone writing about the
results, so every story points to a real customer row you can open and check.

Writes outputs/showcase.json:
    life_events   one customer per mission
    stages        one customer per journey stage (new-home mission where possible)
    next_need     a customer whose next need comes with a clear reason
    stop          a customer with both 'already bought' and 'fatigued' products
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .actions import PLAYBOOK
from .config import EVENT_WEIGHTS, MISSIONS
from .missions import STAGE_ORDER
from .next_need import first_touches, need_in_mission, short_need

MISSION_NAMES = {m.key: m.name for m in MISSIONS}
ACTION = {1.0: "viewed", 3.0: "added to cart", 5.0: "bought"}


def _journey(events: pd.DataFrame, uid: int, mission: str | None) -> list[dict]:
    ue = events[events["user_id"] == uid]
    ft = first_touches(ue)
    out = []
    for r in ft.itertuples():
        in_m = bool(mission) and need_in_mission(r.need, mission)
        out.append({
            "need": r.need,
            "label": short_need(r.need),
            "first_seen": f"{r.t:%d %b}",
            "strongest_action": ACTION.get(float(r.strength), "viewed"),
            "in_mission": in_m,
        })
    return out


def _story(events, actions, recs, supp, uid) -> dict:
    a = actions[actions["user_id"] == uid].iloc[0]
    mission = a["mission"] if isinstance(a["mission"], str) else None
    journey = _journey(events, uid, mission)
    in_m = [j for j in journey if j["in_mission"]] or journey
    days = (events.loc[events["user_id"] == uid, "event_time"].agg(["min", "max"]).diff().iloc[-1]).days
    r = recs[recs["user_id"] == uid].sort_values("rank").head(3)
    s = supp[supp["user_id"] == uid]
    play = PLAYBOOK[a["stage"]]
    return {
        "user_id": int(uid),
        "mission": mission,
        "mission_name": a["mission_name"],
        "stage": a["stage"],
        "days_active": int(days),
        "journey": journey,
        "mission_steps": [j["label"] for j in in_m],
        "next_needs": [{"need": n, "label": short_need(n), "why": w} for n, w in zip(r["need"], r["why"])],
        "stop": [
            {"need": n, "label": short_need(n), "product_id": int(p), "reason": rs}
            for n, p, rs in zip(s["need"], s["product_id"], s["reason"])
        ],
        "job": play["job"],
        "message": play["message"],
        "avoid": play["avoid"],
        "link": f"Customer_Lens?customer={int(uid)}",
    }


def build_showcase(events, actions, missions, recs, supp, out_path: Path) -> dict:
    act = actions.copy()
    span = events.groupby("user_id")["event_time"].agg(lambda s: (s.max() - s.min()).days)
    act["span_days"] = act["user_id"].map(span)
    prim = missions[missions["is_primary"]].drop_duplicates("user_id").set_index("user_id")
    act["mission_needs"] = act["user_id"].map(prim["needs_touched"]).fillna(0)

    def pick(df):
        # rich but readable: many needs inside the mission, inside about a month
        df = df.sort_values(["mission_needs", "mission_score"], ascending=False)
        tight = df[(df["span_days"] <= 35) & (df["mission_needs"].between(4, 8))]
        return (tight if len(tight) else df).iloc[0]["user_id"] if len(df) else None

    life = {}
    for m in MISSIONS:
        uid = pick(act[(act["mission"] == m.key) & (act["stage"] != "Gone quiet")])
        if uid is not None:
            life[m.key] = _story(events, actions, recs, supp, uid)

    stages = {}
    for st in STAGE_ORDER:
        pool = act[act["stage"] == st]
        home = pool[pool["mission"] == "new_home"]
        uid = pick(home if len(home) else pool)
        if uid is not None:
            stages[st] = _story(events, actions, recs, supp, uid)

    nn = act[(act["stage"] == "Next need") & (act["mission"] == "new_home")]
    nxt = _story(events, actions, recs, supp, pick(nn)) if len(nn) else None

    reasons = supp.groupby("user_id")["reason"].agg(set)
    both = [u for u, r in reasons.items() if {"bought", "fatigued"} <= r]
    stop_pool = act[act["user_id"].isin(both) & (act["stage"] != "No mission")]
    stop = _story(events, actions, recs, supp, pick(stop_pool)) if len(stop_pool) else None

    show = {"life_events": life, "stages": stages, "next_need": nxt, "stop": stop,
            "weights": EVENT_WEIGHTS}
    out_path.write_text(json.dumps(show, indent=2, default=str))
    return show
