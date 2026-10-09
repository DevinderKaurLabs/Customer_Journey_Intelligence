"""Shared loaders and styling for the Streamlit app."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from journey.config import MISSIONS, OUTPUTS, PALETTE  # noqa: E402
from journey.missions import STAGE_ORDER, STAGE_RULES  # noqa: E402,F401  (re-exported for pages)
from journey.actions import PLAYBOOK  # noqa: E402,F401  (re-exported for pages)

MISSION_NAMES = {m.key: m.name for m in MISSIONS}
MISSION_SIGNALS = {m.key: m.signal for m in MISSIONS}
NAVY, TEAL, SKY, BEIGE = PALETTE["navy"], PALETTE["teal"], PALETTE["sky"], PALETTE["beige"]

CSS = f"""
<style>
.block-container {{padding-top: 2rem; max-width: 1200px;}}
h1, h2, h3 {{color: {NAVY};}}
.kpi {{background: white; border: 1px solid {SKY}; border-radius: 14px; padding: 16px 18px;}}
.kpi .v {{font-size: 1.9rem; font-weight: 700; color: {NAVY}; line-height: 1.1}}
.kpi .l {{font-size: .85rem; color: #5B6B7C; margin-top: 4px}}
.card {{background: white; border-left: 5px solid {TEAL}; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px}}
.pill {{display:inline-block; padding: 3px 10px; border-radius: 999px; background:{SKY}; color:{NAVY}; font-size:.8rem; margin-right:6px}}
.demo {{background:#FFF7E6; border:1px solid #F0D9A8; border-radius:10px; padding:8px 12px; font-size:.85rem}}
</style>
"""


def setup(title: str) -> None:
    st.set_page_config(page_title=title, page_icon="🧭", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(col, value: str, label: str) -> None:
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)


def _ensure_outputs() -> None:
    if (OUTPUTS / "customer_actions.csv").exists():
        return
    with st.spinner("First run: building demo data and running the pipeline (about 30 seconds)…"):
        if not (ROOT / "data" / "raw" / "demo_events.csv.gz").exists():
            subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo_data.py")], check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "--demo"], check=True)


@st.cache_data(show_spinner=False)
def load_outputs() -> dict:
    _ensure_outputs()
    meta = json.loads((OUTPUTS / "run_meta.json").read_text())
    return {
        "meta": meta,
        "actions": pd.read_csv(OUTPUTS / "customer_actions.csv", parse_dates=["last_active"]),
        "missions": pd.read_csv(OUTPUTS / "missions_now.csv", parse_dates=["first_seen", "last_seen"]),
        "recs": pd.read_csv(OUTPUTS / "recommendations.csv"),
        "supp": pd.read_csv(OUTPUTS / "suppression.csv", parse_dates=["since", "suppress_until"]),
        "transitions": pd.read_csv(OUTPUTS / "transitions.csv"),
        "evaluation": pd.read_csv(OUTPUTS / "evaluation.csv"),
        "depth": pd.read_csv(OUTPUTS / "journey_depth_value.csv"),
    }


@st.cache_data(show_spinner=False)
def load_events() -> pd.DataFrame:
    meta = json.loads((OUTPUTS / "run_meta.json").read_text())
    processed = ROOT / "data" / "processed"
    files = sorted(processed.glob("events_demo.parquet" if meta["demo"] else "events_1in*.parquet"))
    return pd.read_parquet(files[0])


def source_badge(meta: dict) -> None:
    if meta.get("demo"):
        st.markdown(
            '<div class="demo">Running on <b>demo data</b> in the REES46 schema. '
            "Numbers show how the system works — run the pipeline on the real REES46 files for real results.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"Data: {meta['source']}")


def pretty(need: str | float | None) -> str:
    if not isinstance(need, str):
        return "—"
    parts = need.split(".")
    return " › ".join(p.replace("_", " ") for p in parts)
