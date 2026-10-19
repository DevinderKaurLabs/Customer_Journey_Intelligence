"""Customer Journey Intelligence — home."""
import pandas as pd
import streamlit as st

from common import (
    MISSION_NAMES, MISSION_SIGNALS, STAGE_ORDER, kpi, load_outputs, load_showcase, setup, source_badge,
)

setup("Customer Journey Intelligence")
d = load_outputs()
show = load_showcase()
a, ev = d["actions"], d["evaluation"].set_index(["segment", "model"])

st.title("Know the next need before the customer walks in")
st.markdown(
    "Most retargeting shows people the sofa they already bought. This app reads the **pattern** "
    "across what a customer browses — sofa, then bed, then fridge — works out the **life event** behind it "
    "(*setting up a new home*), how far along they are, and what they will need next."
)
source_badge(d["meta"])

c1, c2, c3, c4 = st.columns(4)
in_m = a["stage"] != "No mission"
kpi(c1, f"{a['user_id'].nunique():,}", "active customers scored")
kpi(c2, f"{in_m.mean():.0%}", "show a life-event pattern")
lift = ev.loc[("in a mission", "transitions"), "hit_rate"] / ev.loc[("in a mission", "popularity"), "hit_rate"]
kpi(c3, f"{lift:.1f}x", "better at guessing the next need than 'show what's popular'")
kpi(c4, f"{a['suppressed_products'].sum():,}", "ads to stop showing (bought or ignored)")

st.subheader("See it in action")
st.caption("Four things the app does — each opens a real customer from this data in the Customer Lens.")


def card(col, title, body, uid):
    col.markdown(
        f'<div class="ex"><h4>{title}</h4><p>{body}</p>'
        f'<a href="Customer_Lens?customer={uid}" target="_self">Open this customer →</a></div>',
        unsafe_allow_html=True,
    )


cols = st.columns(4)
life = show.get("life_events", {}).get("new_home")
if life:
    steps = " → ".join(life["mission_steps"][:5])
    card(cols[0], "1 · Spots the life event",
         f"{steps}… in {life['days_active']} days. Not five random clicks — someone setting up a home.", life["user_id"])
rb = show.get("stages", {}).get("Researching")
if rb:
    card(cols[1], "2 · Knows how far along they are",
         f"Comparing {len(rb['mission_steps'])} home categories over several visits, nothing in the cart yet. "
         "Stage: <b>Researching</b> — help them decide.", rb["user_id"])
nn = show.get("next_need")
if nn and nn["next_needs"]:
    top = nn["next_needs"][0]
    card(cols[2], "3 · Predicts the next need",
         f"Next: <b>{top['label']}</b>. Why: {top['why']}.", nn["user_id"])
sp = show.get("stop")
if sp:
    bought = sorted({s["label"] for s in sp["stop"] if s["reason"] == "bought"})
    tired = sorted({s["label"] for s in sp["stop"] if s["reason"] == "fatigued"})
    card(cols[3], "4 · Says what to stop",
         f"Already bought: {', '.join(bought[:3]) or '—'}. Viewed again and again, never carted: "
         f"{', '.join(tired[:3]) or '—'}. Pause those ads.", sp["user_id"])

st.subheader("How it works")
steps = [
    ("1 · Read behaviour", "Every view, add-to-cart and purchase, with its category path (furniture › bedroom › bed)."),
    ("2 · Spot the life event", "A mix of related categories in a short window = a life event, not a one-off purchase."),
    ("3 · Place the stage", "Exploring → Researching → Ready to buy → Next need → Mission complete, or Gone quiet."),
    ("4 · Predict the next need", "Learned from what thousands of customers did next — every prediction says why."),
    ("5 · Act, and stop", "Each stage gets a different message. Bought or ignored products leave the ads."),
]
cols = st.columns(5)
for col, (h, t) in zip(cols, steps):
    col.markdown(f'<div class="card"><b>{h}</b><br><span style="font-size:.9rem">{t}</span></div>', unsafe_allow_html=True)

st.subheader("Life events found")
mix = (
    a[in_m].groupby(["mission_name", "stage"]).size().unstack(fill_value=0)
    .reindex(columns=[s for s in STAGE_ORDER if s in a["stage"].unique()])
)
mix["Total"] = mix.sum(axis=1)
mix = mix.sort_values("Total", ascending=False)
signals = pd.Series({MISSION_NAMES[k]: v for k, v in MISSION_SIGNALS.items()}, name="What the pattern looks like")
st.dataframe(mix.join(signals), width="stretch")

st.caption("Pages on the left: Journey Map → Customer Lens → Next-Need Model → Audiences.")
