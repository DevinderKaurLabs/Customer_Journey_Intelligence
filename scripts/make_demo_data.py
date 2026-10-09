"""Generate a demo clickstream file in the exact REES46 schema.

Why this exists: the real REES46 files are 5-9 GB each and live on Kaggle.
The demo lets anyone clone the repo and see every page of the app in under a
minute. It uses REES46-style category paths and plants realistic multi-step
journeys (with skips, re-ordering, drop-offs and random noise browsing), so the
pipeline has something real to find. Numbers from the demo prove the code
works; numbers for any claim must come from the real data.

Usage:  python scripts/make_demo_data.py --users 15000
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# category_code -> (min price, max price, brands)
CATALOG = {
    # home
    "furniture.living_room.sofa": (300, 1200, ["divan", "lazurit", "askona", "mebelvia"]),
    "furniture.living_room.chair": (50, 300, ["divan", "ikea", "brabix"]),
    "furniture.living_room.cabinet": (80, 500, ["lazurit", "stolline", "ikea"]),
    "furniture.bedroom.bed": (200, 900, ["askona", "ormatek", "lazurit"]),
    "furniture.bedroom.blanket": (20, 80, ["askona", "togas"]),
    "furniture.bedroom.pillow": (10, 50, ["askona", "ormatek"]),
    "furniture.kitchen.table": (80, 400, ["stolline", "ikea", "mebelvia"]),
    "furniture.kitchen.chair": (30, 150, ["stolline", "brabix"]),
    "furniture.bathroom.bath": (150, 700, ["roca", "cersanit", "jacob"]),
    "furniture.universal.light": (15, 150, ["philips", "eglo", "arte"]),
    "appliances.kitchen.refrigerators": (300, 1500, ["samsung", "lg", "bosch", "indesit"]),
    "appliances.kitchen.washer": (250, 900, ["lg", "samsung", "bosch", "beko"]),
    "appliances.kitchen.oven": (200, 800, ["bosch", "electrolux", "gorenje"]),
    "appliances.kitchen.hood": (80, 400, ["elikor", "krona", "bosch"]),
    "appliances.environment.vacuum": (60, 500, ["samsung", "xiaomi", "dyson", "philips"]),
    "appliances.environment.air_conditioner": (250, 900, ["lg", "ballu", "haier"]),
    "construction.tools.drill": (40, 250, ["bosch", "makita", "dewalt"]),
    "construction.tools.saw": (50, 300, ["bosch", "makita", "interskol"]),
    # family
    "kids.carriage": (150, 900, ["cybex", "chicco", "inglesina"]),
    "kids.toys": (10, 120, ["lego", "hasbro", "mattel"]),
    "kids.dolls": (10, 60, ["mattel", "hasbro"]),
    "kids.skates": (25, 120, ["ridex", "tech-team"]),
    "furniture.bedroom.cradle": (80, 400, ["chicco", "ikea", "polini"]),
    "appliances.environment.air_heater": (30, 150, ["ballu", "timberk", "polaris"]),
    "appliances.kitchen.blender": (25, 150, ["philips", "braun", "redmond"]),
    # office
    "computers.notebook": (350, 2000, ["lenovo", "hp", "asus", "apple", "acer"]),
    "computers.desktop": (400, 1800, ["hp", "lenovo", "acer"]),
    "computers.peripherals.monitor": (120, 600, ["samsung", "lg", "aoc", "dell"]),
    "computers.peripherals.mouse": (10, 80, ["logitech", "a4tech", "razer"]),
    "computers.peripherals.keyboard": (15, 150, ["logitech", "a4tech", "razer"]),
    "computers.peripherals.printer": (60, 400, ["hp", "canon", "epson"]),
    "furniture.office.chair": (60, 400, ["brabix", "chairman", "ikea"]),
    "electronics.audio.headphone": (20, 350, ["apple", "sony", "jbl", "samsung"]),
    "stationery.cartrige": (10, 60, ["hp", "canon"]),
    # kitchen
    "appliances.kitchen.microwave": (60, 300, ["samsung", "lg", "midea"]),
    "appliances.kitchen.kettle": (15, 120, ["tefal", "polaris", "redmond"]),
    "appliances.kitchen.coffee_machine": (80, 900, ["delonghi", "philips", "krups"]),
    "appliances.kitchen.toster": (20, 100, ["tefal", "redmond"]),
    "appliances.kitchen.mixer": (25, 200, ["bosch", "kitfort"]),
    "appliances.kitchen.juicer": (30, 250, ["philips", "kitfort"]),
    "appliances.kitchen.meat_grinder": (40, 200, ["bosch", "redmond"]),
    # active
    "sport.bicycle": (150, 1500, ["stels", "forward", "merida"]),
    "sport.trainer": (100, 900, ["torneo", "oxygen", "kettler"]),
    "sport.tennis": (20, 200, ["wilson", "head"]),
    "electronics.clocks": (50, 600, ["apple", "samsung", "xiaomi", "garmin"]),
    "apparel.shoes": (30, 200, ["nike", "adidas", "puma"]),
    "apparel.trousers": (20, 100, ["nike", "adidas"]),
    "accessories.bag": (20, 150, ["samsonite", "xiaomi"]),
    # entertainment
    "electronics.video.tv": (200, 2500, ["samsung", "lg", "sony", "philips"]),
    "electronics.audio.acoustic": (50, 800, ["jbl", "sony", "yamaha"]),
    "electronics.audio.subwoofer": (80, 600, ["jbl", "yamaha"]),
    "electronics.video.projector": (150, 1200, ["epson", "benq"]),
    "electronics.audio.music_tools": (30, 400, ["yamaha", "casio"]),
    # noise / everyday
    "electronics.smartphone": (100, 1400, ["samsung", "apple", "xiaomi", "huawei"]),
    "electronics.tablet": (120, 1200, ["apple", "samsung", "lenovo"]),
    "auto.accessories.player": (30, 200, ["pioneer", "kenwood"]),
    "apparel.costume": (30, 150, ["nike", "adidas"]),
    "accessories.wallet": (15, 80, ["piquadro", "xiaomi"]),
    "country_yard.lawn_mower": (100, 600, ["bosch", "makita"]),
}

# Typical order of a journey. Generator skips, swaps and drops out.
JOURNEYS = {
    "new_home": [
        "furniture.living_room.sofa", "furniture.bedroom.bed", "appliances.kitchen.refrigerators",
        "appliances.kitchen.washer", "furniture.kitchen.table", "furniture.universal.light",
        "appliances.environment.vacuum", "construction.tools.drill", "furniture.kitchen.chair",
        "furniture.living_room.cabinet", "appliances.kitchen.hood", "appliances.kitchen.oven",
        "furniture.bathroom.bath", "furniture.bedroom.blanket", "furniture.bedroom.pillow",
        "appliances.environment.air_conditioner", "construction.tools.saw",
    ],
    "growing_family": [
        "kids.carriage", "furniture.bedroom.cradle", "appliances.environment.air_heater",
        "kids.toys", "appliances.kitchen.blender", "kids.dolls", "kids.skates",
    ],
    "home_office": [
        "computers.notebook", "computers.peripherals.monitor", "computers.peripherals.mouse",
        "computers.peripherals.keyboard", "furniture.office.chair", "electronics.audio.headphone",
        "computers.peripherals.printer", "stationery.cartrige",
    ],
    "kitchen_upgrade": [
        "appliances.kitchen.coffee_machine", "appliances.kitchen.kettle", "appliances.kitchen.microwave",
        "appliances.kitchen.toster", "appliances.kitchen.mixer", "appliances.kitchen.juicer",
        "appliances.kitchen.meat_grinder",
    ],
    "active_lifestyle": [
        "sport.bicycle", "electronics.clocks", "apparel.shoes", "apparel.trousers",
        "accessories.bag", "sport.trainer", "sport.tennis",
    ],
    "entertainment": [
        "electronics.video.tv", "electronics.audio.acoustic", "furniture.living_room.cabinet",
        "electronics.audio.subwoofer", "electronics.video.projector", "electronics.audio.music_tools",
    ],
}
PERSONA_SHARE = {
    "new_home": 0.14, "growing_family": 0.08, "home_office": 0.10, "kitchen_upgrade": 0.07,
    "active_lifestyle": 0.07, "entertainment": 0.06, "casual": 0.48,
}
NOISE = ["electronics.smartphone", "electronics.tablet", "auto.accessories.player",
         "apparel.costume", "accessories.wallet", "country_yard.lawn_mower",
         "electronics.audio.headphone", "appliances.kitchen.kettle"]

START = datetime(2019, 10, 1)
END = datetime(2019, 12, 1)


def build_products(rng: np.random.Generator) -> dict[str, tuple]:
    """category_code -> (product_ids, category_id, brands, prices)."""
    products, pid, cid = {}, 1_000_000, 2_053_013_550_000_000_000
    for code, (lo, hi, brands) in CATALOG.items():
        n = int(rng.integers(15, 40))
        products[code] = (
            np.arange(pid, pid + n),
            cid,
            rng.choice(brands, n),
            np.round(rng.uniform(lo, hi, n), 2),
        )
        pid += n
        cid += 1
    return products


def personalize_order(rng, steps: list[str]) -> list[str]:
    steps = [s for s in steps if rng.random() > 0.35]  # nobody needs everything
    for i in range(len(steps) - 1):  # local re-ordering
        if rng.random() < 0.3:
            steps[i], steps[i + 1] = steps[i + 1], steps[i]
    return steps


def sessions_for_need(rng, user_id, code, t, products, rows, sess_counter, max_purchase_p=0.6):
    """1-4 browsing sessions on one need; may end in cart and purchase."""
    ids, cid, brands, prices = products[code]
    shortlist = rng.choice(len(ids), size=min(len(ids), int(rng.integers(1, 6))), replace=False)
    bought = False
    n_sessions = int(rng.integers(1, 5))
    for s in range(n_sessions):
        sess_counter[0] += 1
        session = f"s{user_id}-{sess_counter[0]}"
        for _ in range(int(rng.integers(2, 9))):
            j = shortlist[int(rng.integers(len(shortlist)))]
            rows.append((t, "view", ids[j], cid, code, brands[j], prices[j], user_id, session))
            t += timedelta(seconds=int(rng.integers(20, 240)))
        if s == n_sessions - 1 and rng.random() < 0.45:
            j = shortlist[0]
            rows.append((t, "cart", ids[j], cid, code, brands[j], prices[j], user_id, session))
            t += timedelta(seconds=int(rng.integers(30, 600)))
            if rng.random() < max_purchase_p:
                rows.append((t, "purchase", ids[j], cid, code, brands[j], prices[j], user_id, session))
                bought = True
        t += timedelta(hours=float(rng.uniform(4, 60)))
    return t, bought


def simulate(n_users: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    products = build_products(rng)
    personas = rng.choice(list(PERSONA_SHARE), n_users, p=list(PERSONA_SHARE.values()))
    rows: list[tuple] = []
    for i, persona in enumerate(personas):
        user_id = 512_000_000 + i * 20  # multiples of 20 survive the default 1-in-20 sampler
        sess_counter = [0]
        t0 = START + timedelta(days=float(rng.uniform(0, 55)), hours=float(rng.uniform(8, 22)))
        if persona == "casual":
            for code in rng.choice(NOISE + list(CATALOG), int(rng.integers(1, 4)), replace=False):
                t = t0 + timedelta(days=float(rng.uniform(0, 40)))
                sessions_for_need(rng, user_id, code, t, products, rows, sess_counter, max_purchase_p=0.4)
            continue
        t = t0
        for code in personalize_order(rng, list(JOURNEYS[persona])):
            if t >= END:
                break
            t, _ = sessions_for_need(rng, user_id, code, t, products, rows, sess_counter)
            t += timedelta(days=float(rng.exponential(3.5)))
            if rng.random() < 0.12:  # drop-off
                break
        for code in rng.choice(NOISE, int(rng.integers(0, 3)), replace=False):  # life is noisy
            tn = t0 + timedelta(days=float(rng.uniform(0, 50)))
            sessions_for_need(rng, user_id, code, tn, products, rows, sess_counter, max_purchase_p=0.3)

    df = pd.DataFrame(rows, columns=["event_time", "event_type", "product_id", "category_id",
                                     "category_code", "brand", "price", "user_id", "user_session"])
    df = df[df["event_time"] < END].sort_values("event_time")
    df["event_time"] = df["event_time"].dt.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=15000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    out = ROOT / "data" / "raw" / "demo_events.csv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = simulate(args.users, args.seed)
    df.to_csv(out, index=False, compression="gzip")
    print(f"Wrote {len(df):,} events for {df.user_id.nunique():,} users -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
