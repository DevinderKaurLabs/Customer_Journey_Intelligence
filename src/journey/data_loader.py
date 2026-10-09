"""Load REES46 clickstream files (or the demo file) into a clean event table.

REES46 schema (one row per event):
    event_time, event_type, product_id, category_id, category_code,
    brand, price, user_id, user_session

The raw monthly files are 5-9 GB, so we stream them in chunks and keep a
deterministic 1-in-N sample of users. Sampling by user (not by row) keeps every
journey whole, which is the entire point of this project.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DATA_PROCESSED, DATA_RAW, PipelineConfig

USECOLS = [
    "event_time",
    "event_type",
    "product_id",
    "category_code",
    "brand",
    "price",
    "user_id",
    "user_session",
]
DTYPES = {
    "event_type": "category",
    "product_id": "int64",
    "category_code": "string",
    "brand": "string",
    "price": "float32",
    "user_id": "int64",
    "user_session": "string",
}


def need_of(category_code: pd.Series, depth: int = 3) -> pd.Series:
    """`appliances.kitchen.refrigerators` -> itself; deeper codes are cut to 3 levels.

    A "need" is the unit we recommend: specific enough to act on
    ("a bed"), general enough to have data ("not this exact bed").
    """
    return category_code.str.split(".").str[:depth].str.join(".")


def _read_one(path: Path, cfg: PipelineConfig, chunksize: int = 2_000_000) -> pd.DataFrame:
    parts = []
    for chunk in pd.read_csv(path, usecols=USECOLS, dtype=DTYPES, chunksize=chunksize):
        chunk = chunk[chunk["user_id"] % cfg.user_sample_mod == 0]
        chunk = chunk.dropna(subset=["category_code"])
        parts.append(chunk)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=USECOLS)


def clean(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()
    df["event_time"] = pd.to_datetime(
        df["event_time"].astype(str).str.replace(" UTC", "", regex=False), utc=True
    ).dt.tz_localize(None)
    df["event_type"] = df["event_type"].astype(str).str.lower()
    df = df[df["event_type"].isin(["view", "cart", "purchase"])]
    df = df.dropna(subset=["category_code", "user_id", "user_session"])
    df = df[df["price"] > 0]
    df["brand"] = df["brand"].fillna("unknown")
    df["need"] = need_of(df["category_code"])
    df["dept"] = df["category_code"].str.split(".").str[0]
    df = df.drop_duplicates(["user_id", "user_session", "product_id", "event_type", "event_time"])
    return df.sort_values(["user_id", "event_time"]).reset_index(drop=True)


def load_events(cfg: PipelineConfig | None = None, demo: bool = False, refresh: bool = False) -> pd.DataFrame:
    """Return clean events, caching a parquet in data/processed/."""
    cfg = cfg or PipelineConfig()
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    cache = DATA_PROCESSED / ("events_demo.parquet" if demo else f"events_1in{cfg.user_sample_mod}.parquet")
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)

    if demo:
        files = [DATA_RAW / "demo_events.csv.gz"]
        if not files[0].exists():
            raise FileNotFoundError("Demo file missing. Run: python scripts/make_demo_data.py")
        demo_cfg = PipelineConfig(user_sample_mod=1)
        raw = pd.concat([_read_one(f, demo_cfg) for f in files], ignore_index=True)
    else:
        files = [DATA_RAW / f for f in cfg.files]
        missing = [str(f) for f in files if not f.exists()]
        if missing:
            raise FileNotFoundError(
                "Real REES46 files not found: "
                + ", ".join(missing)
                + "\nRun: python scripts/download_data.py  (or use --demo)"
            )
        raw = pd.concat([_read_one(f, cfg) for f in files], ignore_index=True)

    events = clean(raw)
    events.to_parquet(cache, index=False)
    return events
