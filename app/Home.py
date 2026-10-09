"""Customer Journey Intelligence — home."""
import pandas as pd
import streamlit as st

from common import MISSION_NAMES, MISSION_SIGNALS, STAGE_ORDER, kpi, load_outputs, setup, source_badge

setup("Customer Journey Intelligence")
d = load_outputs()
a, ev = d["actions"], d["evaluation"].set_index(["segment", "model"])

st.title("Know the next need before the customer walks in")
st.markdown(
    "Most retargeting shows people the sofa they already bought. This system reads the **pattern** "
    "across what a customer browses — sofa, then bed, then fridge — works out the **life mission** behind it "
    "(*setting up a new home*), how far along they are, and what they will need next."
)
source_badge(d["meta"])
st.write("")

c1, c2, c3, c4 = st.columns(4)
in_m = a["stage"] != "No mission"
kpi(c1, f"{a['user_id'].nunique():,}", "active customers scored")
kpi(c2, f"{in_m.mean():.0%}", "show a life-mission pattern")
lift = ev.loc[("in a mission", "transitions"), "hit_rate"] / ev.loc[("in a mission", "popularity"), "hit_rate"]
kpi(c3, f"{lift:.1f}x", "better at guessing the next need than 'popular' (mission customers)")
kpi(c4, f"{a['suppressed_products'].sum():,}", "ads to stop showing (bought or fatigued)")

st.subheader("How it works")
steps = [
    ("1 · Read behaviour", "Every view, add-to-cart and purchase, with its category path (e.g. furniture › bedroom › bed)."),
    ("2 · Detect the mission", "Breadth across related needs in a short window = a life event, not a single purchase."),
    ("3 · Place the stage", "Exploring → Researching → Ready to buy → Next need → Mission complete (or Gone quiet)."),
    ("4 · Predict the next need", "Learned from what thousands of customers did next — every prediction comes with its reason."),
    ("5 · Act, and stop", "Each stage gets a different job. Bought or fatigued products are suppressed."),
]
cols = st.columns(5)
for col, (h, t) in zip(cols, steps):
    col.markdown(f'<div class="card"><b>{h}</b><br><span style="font-size:.9rem">{t}</span></div>', unsafe_allow_html=True)

st.subheader("Missions found")
mix = (
    a[in_m].groupby(["mission_name", "stage"]).size().unstack(fill_value=0)
    .reindex(columns=[s for s in STAGE_ORDER if s in a["stage"].unique()])
)
mix["Total"] = mix.sum(axis=1)
mix = mix.sort_values("Total", ascending=False)
signals = pd.Series({MISSION_NAMES[k]: v for k, v in MISSION_SIGNALS.items()}, name="What the pattern looks like")
st.dataframe(mix.join(signals), width="stretch")

st.caption("Use the pages on the left: Journey Map → Customer Lens → Next-Need Model → Audiences.")
