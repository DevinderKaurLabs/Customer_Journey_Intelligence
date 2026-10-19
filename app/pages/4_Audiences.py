"""Audiences: mission x stage segments, ready to export, with the job each one gets."""
import streamlit as st

from common import PLAYBOOK, STAGE_ORDER, kpi, load_outputs, pretty, setup, source_badge

setup("Audiences")
d = load_outputs()
a, supp, depth = d["actions"], d["supp"], d["depth"]

st.title("Audiences")
st.markdown("Every segment below is **mission × stage**. Each gets a different job — and a list of things *not* to show.")
source_badge(d["meta"])

c1, c2 = st.columns(2)
m_pick = c1.multiselect("Missions", sorted(a["mission_name"].unique()), default=[])
s_pick = c2.multiselect("Stages", [s for s in STAGE_ORDER + ["No mission"] if s in a["stage"].unique()], default=["Next need"])
aud = a.copy()
if m_pick:
    aud = aud[aud["mission_name"].isin(m_pick)]
if s_pick:
    aud = aud[aud["stage"].isin(s_pick)]

k1, k2, k3 = st.columns(3)
kpi(k1, f"{len(aud):,}", "customers in this audience")
kpi(k2, f"{aud['next_need_opportunity'].median():,.0f}", "median next-need opportunity (prioritisation score)")
kpi(k3, f"{supp[supp['user_id'].isin(aud['user_id'])].shape[0]:,}", "product ads to suppress for them")

st.subheader("What to do with them")
for stage in (s_pick or aud["stage"].unique()):
    p = PLAYBOOK[stage]
    st.markdown(f'<div class="card"><b>{stage} → {p["job"]}</b><br>{p["message"]}<br>'
                f'<span style="font-size:.85rem;color:#5B6B7C">Channel: {p["channel"]} · Avoid: {p["avoid"]}</span></div>',
                unsafe_allow_html=True)

st.subheader("Most common next needs in this audience")
nn = aud["next_need_1"].value_counts().head(10).rename_axis("need").reset_index(name="customers")
nn["need"] = nn["need"].map(pretty)
st.dataframe(nn, hide_index=True, width="stretch")

cols = ["user_id", "mission_name", "stage", "next_need_1", "next_need_2", "next_need_3", "job", "next_need_opportunity", "suppressed_products"]
st.download_button("Download audience (CSV)", aud[cols].to_csv(index=False), "audience.csv", "text/csv")
st.download_button("Download suppression list (CSV)", supp[supp["user_id"].isin(aud["user_id"])].to_csv(index=False),
                   "suppression.csv", "text/csv")

st.subheader("Why journeys matter for lifetime value")
depth = depth.assign(repeat_rate=(depth["repeat_rate"] * 100).round(0).astype(int).astype(str) + "%",
                     avg_next_spend=depth["avg_next_spend"].round(0).astype(int))
st.dataframe(depth.rename(columns={"group": "Before the cutoff", "repeat_rate": "Bought again (next 30d)",
                                   "avg_next_spend": "Avg next-30d spend", "avg_next_orders": "Avg next-30d orders",
                                   "customers": "Customers"}).round(2), hide_index=True, width="stretch")
st.caption("Descriptive, not causal: customers deeper into a mission may simply be more engaged. "
           "The 'next-need opportunity' is a prioritisation heuristic (likelihood × typical basket), not a revenue forecast.")
