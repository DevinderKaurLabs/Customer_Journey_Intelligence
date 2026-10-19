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
from journey.missions import STAGE_ORDER, STAGE_RULES  # noqa: E402,F401  # re-exported for pages
from journey.actions import PLAYBOOK  # noqa: E402,F401  # re-exported for pages

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
.src {{font-size:.8rem; color:#5B6B7C; margin:-6px 0 14px}}
.track {{display:flex; flex-wrap:wrap; gap:6px; margin:4px 0 14px}}
.step {{padding:6px 12px; border-radius:999px; font-size:.82rem; background:white; border:1px solid {SKY}; color:#5B6B7C}}
.step.on {{background:{NAVY}; border-color:{NAVY}; color:white; font-weight:600}}
.step.quiet {{border-style:dashed}}
.ex {{background:white; border:1px solid {SKY}; border-radius:14px; padding:16px 18px; height:100%}}
.ex h4 {{margin:0 0 6px; color:{NAVY}; font-size:1rem}}
.ex p {{margin:0 0 8px; font-size:.88rem; color:#33475B}}
</style>
"""


def setup(title: str) -> None:
    st.set_page_config(page_title=title, page_icon="🧭", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(col, value: str, label: str) -> None:
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)


def _ensure_outputs() -> None:
    needed = [OUTPUTS / "customer_actions.csv", OUTPUTS / "showcase.json"]
    has_events = any((ROOT / "data" / "processed").glob("events_*.parquet"))
    if all(p.exists() for p in needed) and has_events:
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
            '<div class="src">Demo mode: sample customers in the REES46 format and category tree. '
            "Point the pipeline at the real REES46 files to see your own numbers.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="src">Data: {meta["source"]}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_showcase() -> dict:
    _ensure_outputs()
    p = OUTPUTS / "showcase.json"
    return json.loads(p.read_text()) if p.exists() else {}


def stage_track(current: str) -> str:
    """The journey ladder as pills, current stage highlighted."""
    steps = [s for s in STAGE_ORDER if s != "Gone quiet"]
    html = "".join(f'<span class="step{" on" if s == current else ""}">{s}</span>' for s in steps)
    html += f'<span class="step quiet{" on" if current == "Gone quiet" else ""}">Gone quiet</span>'
    return f'<div class="track">{html}</div>'


def label(need: str | float | None) -> str:
    """'furniture.living_room.sofa' -> 'sofa'."""
    return need.split(".")[-1].replace("_", " ") if isinstance(need, str) else "—"


def pretty(need: str | float | None) -> str:
    if not isinstance(need, str):
        return "—"
    parts = need.split(".")
    return " › ".join(p.replace("_", " ") for p in parts)
