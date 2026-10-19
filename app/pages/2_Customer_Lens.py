"""Customer Lens: one customer, end to end — what they did, what we think, what we do."""
import plotly.express as px
import streamlit as st

from common import (
    MISSION_NAMES, NAVY, PLAYBOOK, SKY, STAGE_ORDER, STAGE_RULES, TEAL,
    label, load_events, load_outputs, pretty, setup, source_badge, stage_track,
)
from journey.suppression import alternatives

setup("Customer Lens")
d = load_outputs()
a, recs, supp, missions = d["actions"], d["recs"], d["supp"], d["missions"]

st.title("Customer Lens")
st.markdown("Pick a customer. See the journey, the mission we detected, the stage, the next need, and what we'd **stop** showing them.")
source_badge(d["meta"])

# a link like ?customer=512038320 opens that customer directly
qp_uid = None
try:
    qp_uid = int(st.query_params.get("customer", ""))
except ValueError:
    pass
qp_row = a[a["user_id"] == qp_uid].iloc[0] if qp_uid in set(a["user_id"]) else None

c1, c2, c3 = st.columns(3)
mission_opts = ["Any"] + sorted(a["mission_name"].dropna().unique().tolist())
m_default = qp_row["mission_name"] if qp_row is not None else "Setting up a new home"
m_pick = c1.selectbox("Mission", mission_opts, index=mission_opts.index(m_default) if m_default in mission_opts else 0)
stages = ["Any"] + [s for s in STAGE_ORDER + ["No mission"] if s in a["stage"].unique()]
s_default = qp_row["stage"] if qp_row is not None else "Next need"
s_pick = c2.selectbox("Stage", stages, index=stages.index(s_default) if s_default in stages else 0)
pool = a.copy()
if m_pick != "Any":
    pool = pool[pool["mission_name"] == m_pick]
if s_pick != "Any":
    pool = pool[pool["stage"] == s_pick]
pool = pool.sort_values("mission_score", ascending=False)
if pool.empty:
    st.warning("No customers match. Loosen the filters.")
    st.stop()
options = pool["user_id"].head(300).tolist()
if qp_uid in set(pool["user_id"]) and qp_uid not in options[:1]:
    options = [qp_uid] + [o for o in options if o != qp_uid]
uid = c3.selectbox("Customer", options)
st.query_params["customer"] = str(uid)
row = a[a["user_id"] == uid].iloc[0]

# ---- the read
left, right = st.columns([1.1, 1])
with left:
    st.subheader("What we think is going on")
    st.markdown(stage_track(row["stage"]), unsafe_allow_html=True)
    st.markdown(
        f'<div class="card"><span class="pill">{row["mission_name"]}</span><span class="pill">{row["stage"]}</span>'
        f'<br><br>{STAGE_RULES.get(row["stage"], "No multi-category pattern — treat as a single-product shopper.")}'
        f'<br><br><b>{row["needs_touched"]}</b> needs explored · <b>{row["needs_bought"]}</b> bought · '
        f'last active {row["last_active"]:%d %b %Y}</div>',
        unsafe_allow_html=True,
    )
    um = missions[missions["user_id"] == uid].sort_values("score", ascending=False)
    if len(um) > 1:
        st.caption("Other missions this customer also shows: " + ", ".join(
            f"{MISSION_NAMES[m]} ({s})" for m, s in zip(um["mission"].iloc[1:], um["stage"].iloc[1:])))
with right:
    play = PLAYBOOK[row["stage"]]
    st.subheader(f"Job: {play['job']}")
    st.markdown(
        f'<div class="card"><b>Say</b>: {play["message"]}<br><b>Where</b>: {play["channel"]}'
        f'<br><b>Don\'t</b>: {play["avoid"]}</div>', unsafe_allow_html=True)

# ---- the timeline
ev = load_events()
ue = ev[ev["user_id"] == uid].copy()
ue["Need"] = ue["need"].map(label)
order = ue.groupby("Need")["event_time"].min().sort_values().index.tolist()
st.subheader("The journey so far")
fig = px.scatter(
    ue, x="event_time", y="Need", color="event_type", symbol="event_type",
    category_orders={"Need": order, "event_type": ["view", "cart", "purchase"]},
    color_discrete_map={"view": SKY, "cart": TEAL, "purchase": NAVY},
    hover_data={"brand": True, "price": ":.2f", "product_id": True, "event_time": "|%d %b %H:%M"},
)
fig.update_traces(marker=dict(size=11, line=dict(width=1, color="white")))
fig.update_layout(height=max(260, 34 * len(order) + 90), margin=dict(l=10, r=10, t=10, b=10),
                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white", legend_title_text="", yaxis_title="", xaxis_title="")
st.plotly_chart(fig, width="stretch")

# ---- next need + stop list
n1, n2 = st.columns(2)
with n1:
    st.subheader("Show next")
    r = recs[recs["user_id"] == uid].sort_values("rank")
    for _, x in r.iterrows():
        st.markdown(f'<div class="card"><b>{x["rank"]}. {label(x["need"]).capitalize()}</b>'
                    f' <span style="font-size:.8rem;color:#5B6B7C">({pretty(x["need"])})</span><br>'
                    f'<span style="font-size:.88rem;color:#33475B">Why: {x["why"]}</span></div>',
                    unsafe_allow_html=True)
with n2:
    st.subheader("Stop showing")
    s = supp[supp["user_id"] == uid]
    if s.empty:
        st.write("Nothing to suppress yet.")
    else:
        s = s.sort_values(["reason", "suppress_until"], ascending=[True, False])
        if len(s) > 6:
            st.caption(f"Showing 6 of {len(s)} paused products.")
        for _, x in s.head(6).iterrows():
            why = "Already bought" if x["reason"] == "bought" else "Seen many times, never added to cart"
            st.markdown(f'<div class="card"><b>{label(x["need"]).capitalize()}</b> · product {x["product_id"]}<br>'
                        f'<span style="font-size:.85rem">{why} — paused until {x["suppress_until"]:%d %b}</span></div>',
                        unsafe_allow_html=True)
        fat = s[s["reason"] == "fatigued"]
        if not fat.empty:
            alt = alternatives(ev, int(fat["product_id"].iloc[0]))
            if not alt.empty:
                st.caption(f"Instead of product {fat['product_id'].iloc[0]} again, try a different brand at a similar price:")
                st.dataframe(alt.rename(columns={"buyers": "bought by others"}), hide_index=True, width="stretch")
