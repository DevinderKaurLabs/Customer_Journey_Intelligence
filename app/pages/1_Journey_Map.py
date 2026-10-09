"""Journey Map: how customers move from one need to the next inside a mission."""
import plotly.graph_objects as go
import streamlit as st

from common import MISSIONS, MISSION_NAMES, NAVY, TEAL, load_outputs, pretty, setup, source_badge
from journey.next_need import need_in_mission

setup("Journey Map")
d = load_outputs()
tr = d["transitions"]

st.title("Journey Map")
st.markdown("Where customers go **next** after each need. Thicker flow = more customers took that path.")
source_badge(d["meta"])

c1, c2, c3 = st.columns([2, 1, 1])
mission_key = c1.selectbox("Mission", [m.key for m in MISSIONS], format_func=MISSION_NAMES.get)
min_support = c2.slider("Min customers per path", 5, 300, 40, step=5)
max_links = c3.slider("Max paths shown", 10, 60, 25, step=5)

t = tr[
    tr["from_need"].apply(lambda n: need_in_mission(n, mission_key))
    & tr["to_need"].apply(lambda n: need_in_mission(n, mission_key))
    & (tr["support"] >= min_support)
].sort_values("weight", ascending=False).head(max_links)

if t.empty:
    st.info("No paths at this threshold — lower 'Min customers per path'.")
else:
    # two columns of nodes (from -> to) keep the Sankey acyclic and readable
    src_nodes = sorted(t["from_need"].unique())
    dst_nodes = sorted(t["to_need"].unique())
    labels = [pretty(n).split(" › ", 1)[-1] for n in src_nodes] + ["→ " + pretty(n).split(" › ", 1)[-1] for n in dst_nodes]
    idx_s = {n: i for i, n in enumerate(src_nodes)}
    idx_d = {n: i + len(src_nodes) for i, n in enumerate(dst_nodes)}
    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=14, thickness=14, color=[NAVY] * len(src_nodes) + [TEAL] * len(dst_nodes)),
        link=dict(
            source=[idx_s[x] for x in t["from_need"]],
            target=[idx_d[x] for x in t["to_need"]],
            value=t["support"].tolist(),
            color="rgba(200,217,230,0.65)",
            customdata=(t["prob"] * 100).round(0),
            hovertemplate="%{source.label} → %{target.label}<br>%{value} customers · %{customdata}% of onward journeys<extra></extra>",
        ),
    ))
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", font=dict(size=12))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Strongest next steps in this mission")
    show = t.sort_values("prob", ascending=False).head(10).assign(
        From=lambda x: x["from_need"].map(pretty), Next=lambda x: x["to_need"].map(pretty),
        **{"Share going on to this": lambda x: (x["prob"] * 100).round(0).astype(int).astype(str) + "%", "Customers": lambda x: x["support"]},
    )[["From", "Next", "Share going on to this", "Customers"]]
    st.dataframe(show, hide_index=True, width="stretch")

st.caption(
    "Paths are learned from the order in which each customer first engaged with each need (up to 3 steps ahead, "
    "closer steps weighted more). A path is a pattern across many customers — not a rule for any one of them."
)
