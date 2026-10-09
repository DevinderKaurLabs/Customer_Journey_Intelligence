"""Small hand-built journeys so each rule is tested on behaviour we can reason about."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from journey.config import PipelineConfig  # noqa: E402
from journey.data_loader import clean, need_of  # noqa: E402
from journey.missions import score_missions  # noqa: E402
from journey.next_need import NextNeedModel, first_touches, holdout_targets  # noqa: E402
from journey.suppression import retargeting_waste, suppression_list  # noqa: E402

T0 = pd.Timestamp("2019-10-01 10:00")


def ev(user, day, etype, code, pid, session=None, price=100.0, brand="b"):
    return {
        "event_time": f"{T0 + pd.Timedelta(days=day):%Y-%m-%d %H:%M:%S} UTC",
        "event_type": etype, "product_id": pid, "category_code": code, "brand": brand,
        "price": price, "user_id": user, "user_session": session or f"{user}-{day}",
    }


@pytest.fixture
def events():
    rows = []
    # user 1: classic new-home journey - sofa (bought), bed, fridge in cart
    rows += [ev(1, 0, "view", "furniture.living_room.sofa", 10), ev(1, 0, "view", "furniture.living_room.sofa", 11),
             ev(1, 1, "cart", "furniture.living_room.sofa", 10), ev(1, 1, "purchase", "furniture.living_room.sofa", 10),
             ev(1, 5, "view", "furniture.bedroom.bed", 20), ev(1, 9, "view", "appliances.kitchen.refrigerators", 30),
             ev(1, 9, "cart", "appliances.kitchen.refrigerators", 30)]
    # user 2: one smartphone only -> no mission
    rows += [ev(2, d, "view", "electronics.smartphone", 40, session=f"2-{d}") for d in range(6)]
    # users 3-12 teach the model: sofa -> bed -> fridge
    for u in range(3, 13):
        rows += [ev(u, 0, "view", "furniture.living_room.sofa", 10), ev(u, 3, "view", "furniture.bedroom.bed", 20),
                 ev(u, 6, "view", "appliances.kitchen.refrigerators", 30)]
    return clean(pd.DataFrame(rows))


def test_need_depth():
    s = pd.Series(["a.b.c.d", "a.b"], dtype="string")
    assert need_of(s).tolist() == ["a.b.c", "a.b"]


def test_mission_detected_only_with_breadth(events):
    cfg = PipelineConfig(mission_min_score=1.0)
    m = score_missions(events, T0 + pd.Timedelta(days=10), cfg)
    assert 1 in set(m["user_id"])  # 3 needs in new_home
    assert 2 not in set(m["user_id"])  # smartphone is not a mission


def test_stage_ready_to_buy_beats_next_need(events):
    cfg = PipelineConfig(mission_min_score=1.0)
    m = score_missions(events, T0 + pd.Timedelta(days=10), cfg)
    row = m[(m.user_id == 1) & (m.mission == "new_home")].iloc[0]
    assert row["needs_bought"] == 1
    assert row["stage"] == "Ready to buy"  # open fridge cart outranks "next need"


def test_gone_quiet(events):
    cfg = PipelineConfig(mission_min_score=0.1)
    m = score_missions(events, T0 + pd.Timedelta(days=40), cfg)
    assert m[(m.user_id == 1) & (m.mission == "new_home")]["stage"].iloc[0] == "Gone quiet"


def test_transitions_learn_order(events):
    model = NextNeedModel().fit(events)
    t = model.transitions.set_index(["from_need", "to_need"])
    assert t.loc[("furniture.living_room.sofa", "furniture.bedroom.bed"), "prob"] > \
        t.loc[("furniture.living_room.sofa", "appliances.kitchen.refrigerators"), "prob"]


def test_recommend_excludes_seen_and_explains(events):
    model = NextNeedModel().fit(events)
    ft = first_touches(events[events.user_id == 3])
    ft = ft[ft["need"] == "furniture.living_room.sofa"]
    r = model.recommend(ft, k=3)
    assert r["need"].iloc[0] == "furniture.bedroom.bed"
    assert "furniture.living_room.sofa" not in set(r["need"])
    assert r["why"].iloc[0].startswith("after furniture.living_room.sofa")


def test_suppression_bought_and_fatigued(events):
    extra = clean(pd.DataFrame([ev(50, d, "view", "electronics.video.tv", 99, session=f"50-{d}") for d in range(6)]))
    allev = pd.concat([events, extra])
    s = suppression_list(allev, T0 + pd.Timedelta(days=10))
    assert ((s.user_id == 1) & (s.product_id == 10) & (s.reason == "bought")).any()
    assert ((s.user_id == 50) & (s.product_id == 99) & (s.reason == "fatigued")).any()


def test_retargeting_waste_counts_bought(events):
    w = retargeting_waste(events, T0 + pd.Timedelta(days=10))
    assert w["slots_already_bought_product"] >= 1
    assert 0 < w["share_product_bought"] < 1


def test_holdout_only_new_needs(events):
    t = holdout_targets(events, T0 + pd.Timedelta(days=4), horizon_days=30)
    assert "furniture.living_room.sofa" not in t.loc[1, "new_needs"]
    assert "furniture.bedroom.bed" in t.loc[1, "new_needs"]
